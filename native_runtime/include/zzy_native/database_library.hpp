#pragma once
namespace zzy {
inline void ExecutionContext::database_transaction(const std::vector<Value>& args,NodeId site,Done done) {
#ifdef ZZY_NATIVE_SQLITE
    if(database) error(site,"E401","不支持嵌套事务");
    const auto& callback=object(args[1]);
    if(callback.syntax==no_node || ast(callback.syntax).kind=="lazy" || ast(callback.syntax).children.size()!=1)
        error(site,"E201","事务需要零参数ZZY函数");
    const auto& chars=object(args[0]).characters;
    const auto count=utf8_size(chars);check("io_payload_bytes",count,site);
    Lease encoded(heap.state,{0,0,count},site);
    const auto path=encode_utf8(chars);
    if(path.find('\0')!=std::string::npos) error(site,"E401","SQLite事务失败");
    try {
        auto connection=std::make_shared<sqlite_host::Connection>(heap.state,site);
        const auto& api=connection->api;
        const auto status=api.open_v2(path.c_str(),&connection->value,SQLITE_OPEN_READWRITE|SQLITE_OPEN_CREATE|SQLITE_OPEN_NOMUTEX,nullptr);
        point();
        sqlite_host::require_ok(status);
        api.limit(connection->value,SQLITE_LIMIT_LENGTH,static_cast<int>(std::min<std::uint64_t>(1000000000,heap.state->policy.limits.at("io_payload_bytes"))));
        api.limit(connection->value,SQLITE_LIMIT_SQL_LENGTH,static_cast<int>(std::min<std::uint64_t>(1000000000,heap.state->policy.limits.at("io_payload_bytes"))));
        sqlite_host::require_ok(api.busy_handler(connection->value,sqlite_host::Connection::busy,connection.get()));
        connection->plain("BEGIN IMMEDIATE");point();
        database=connection;
        encoded.release();
        call(args[1],{},site,[this,connection,site,done=std::move(done)](Value value) {
            if(object(value).kind!="Result") error(site,"E201","事务回调必须返回Result");
            point();connection->clear_guards();
            try {
                if(object(value).flag) connection->plain("COMMIT");
                else connection->plain("ROLLBACK");
                if(!connection->close()) throw sqlite_host::Failure{};
            } catch(const sqlite_host::Failure&) {point();error(site,"E401","SQLite事务失败");}
            database.reset();
            // The Result already exists before COMMIT; subsequent language
            // output/allocation failures cannot undo this completed transaction.
            done(value);
        });
    } catch(const sqlite_host::Failure&) {point();error(site,"E401","SQLite事务失败");}
#else
    (void)args;(void)done;error(site,"E402","native SQLite capability is disabled");
#endif
}

inline Value ExecutionContext::database_query(const std::vector<Value>& args,NodeId site) {
#ifdef ZZY_NATIVE_SQLITE
    if(!database) error(site,"E401","query需要活动事务");
    auto& connection=*database;connection.check_thread();
    const auto& api=connection.api;
    struct Guards {
        sqlite_host::Connection& value;
        ~Guards() {value.clear_guards();}
    } guards{connection};
    const auto check_status=[&](int status) {
        point();
        if(status==SQLITE_NOMEM) throw std::bad_alloc();
        if(status!=SQLITE_OK) error(site,"E401","SQLite查询失败");
    };
    const auto deadline=[&] {
        point();
        if(std::chrono::steady_clock::now()>=connection.deadline) error(site,"E401","SQLite执行超时");
    };
    connection.deadline=std::chrono::steady_clock::now()+std::chrono::seconds(1);connection.timed=true;
    api.progress_handler(connection.value,1000,sqlite_host::Connection::progress,&connection);
    check_status(api.set_authorizer(connection.value,sqlite_host::Connection::authorize,nullptr));
    const auto& chars=object(args[0]).characters;
    const auto count=utf8_size(chars);check("io_payload_bytes",count,site);
    Lease sql_bytes(heap.state,{0,0,count},site);
    const auto sql=encode_utf8(chars);
    if(sql.find('\0')!=std::string::npos) error(site,"E401","SQLite查询失败");
    const auto& params=object(args[1]).edges;
    Lease parameter_slots(heap.state,{0,params.size(),0},site);
    // Match the existing boundary: validate every parameter before preparing SQL.
    for(const auto handle:params) {
        point();const auto& value=heap.state->get(handle);
        if(value.kind!="Null" && value.kind!="Int" && value.kind!="Float" && value.kind!="String") error(site,"E201","不支持SQLite参数类型");
        if(value.kind=="Int" && (value.integer<BigInt(INT64_MIN) || value.integer>BigInt(INT64_MAX))) error(site,"E208","SQLite Int超出64位");
        if(value.kind=="String") check("io_payload_bytes",utf8_size(value.characters),site);
    }
    Lease bound_text(heap.state,{},site);
    sqlite_host::Statement statement(connection.api);
    const char* tail=nullptr;
    check_status(api.prepare_v2(connection.value,sql.c_str(),-1,&statement.value,&tail));deadline();
    // A second prepared statement is rejected before stepping the first one.
    while(tail && tail<sql.c_str()+sql.size()) {
        deadline();sqlite_host::Statement extra(connection.api);const char* next=nullptr;
        check_status(api.prepare_v2(connection.value,tail,-1,&extra.value,&next));
        if(extra.value || !next || next<=tail) error(site,"E401","SQLite查询失败");
        tail=next;
    }
    if(static_cast<std::size_t>(statement.value?api.bind_parameter_count(statement.value):0)!=params.size()) error(site,"E401","SQLite查询失败");
    for(std::size_t i=0;i<params.size();++i) {
        deadline();const auto& value=heap.state->get(params[i]);const auto index=static_cast<int>(i+1);
        if(value.kind=="Null") check_status(api.bind_null(statement.value,index));
        else if(value.kind=="Int") {
            const auto magnitude=std::uint64_t(value.integer.word(0))|(std::uint64_t(value.integer.word(1))<<32);
            const auto number=value.integer.sign()<0?(magnitude==(UINT64_C(1)<<63)?INT64_MIN:-static_cast<std::int64_t>(magnitude)):static_cast<std::int64_t>(magnitude);
            check_status(api.bind_int64(statement.value,index,number));
        } else if(value.kind=="Float") check_status(api.bind_double(statement.value,index,value.real));
        else {
            const auto size=utf8_size(value.characters);Lease bytes(heap.state,{0,0,size},site);
            if(size>INT_MAX) error(site,"E401","SQLite查询失败");
            const auto encoded=encode_utf8(value.characters);
            bound_text.grow({0,0,size},site);
            check_status(api.bind_text(statement.value,index,encoded.data(),static_cast<int>(size),SQLITE_TRANSIENT));
        }
    }
    auto rows=array({},site);
    if(!statement.value) return rows;
    for(;;) {
        deadline();const auto status=api.step(statement.value);deadline();
        if(status==SQLITE_DONE) break;
        if(status!=SQLITE_ROW) check_status(status);
        check("value_depth",1,site);
        auto row=array({},site);
        for(int i=0;i<api.column_count(statement.value);++i) {
            deadline();Value cell;
            switch(api.column_type(statement.value,i)) {
                case SQLITE_NULL:cell=null_;break;
                case SQLITE_INTEGER:cell=integer(BigInt(api.column_int64(statement.value,i)),site);break;
                case SQLITE_FLOAT: {
                    const auto value=api.column_double(statement.value,i);
                    if(!std::isfinite(value)) error(site,"E201","不支持SQLite结果类型");
                    cell=real(value,site);break;
                }
                case SQLITE_TEXT: {
                    const auto* text=api.column_text(statement.value,i);
                    if(!text && api.errcode(connection.value)==SQLITE_NOMEM) throw std::bad_alloc();
                    const auto size=static_cast<std::size_t>(api.column_bytes(statement.value,i));
                    if(!text && size) error(site,"E401","SQLite查询失败");
                    check("io_payload_bytes",size,site);
                    const std::string_view bytes(text?reinterpret_cast<const char*>(text):"",size);
                    const auto points=codepoints(bytes);check("text_codepoints",points,site);
                    Lease decoded(heap.state,{0,0,4*points},site);std::u32string value;value.reserve(points);
                    try {for(std::size_t j=0;j<size;) {if((j&4095)==0) deadline();value+=utf8_next(bytes,j);}}
                    catch(const std::invalid_argument&) {error(site,"E401","SQLite查询失败");}
                    decoded.release();cell=string(std::move(value),site);break;
                }
                default:error(site,"E201","不支持SQLite结果类型");
            }
            append(row,cell,site);
        }
        append(rows,row,site);
    }
    return rows;
#else
    (void)args;error(site,"E402","native SQLite capability is disabled");
#endif
}
}
