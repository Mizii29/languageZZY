"""Optional independent Draft 2020-12 oracle, collected by tests.web_http."""
import unittest
from jsonschema import Draft202012Validator
from tests.test_contracts import compiled, invoke
from zzy.contracts import ContractViolation, openapi


class SchemaTests(unittest.TestCase):
    def test_adapter_errors_share_status_with_business_contract(self):
        bindings={'POST /api/test':{'request':'Input','responses':{'422':'Input','500':'Input','503':'Input'}}}
        with compiled('(shape) Input {message:(String);}',bindings) as bundle:
            document=openapi(bundle[1],bundle[2],bundle[3])
            for status,body in [('422',{'error':{'code':'contract_input','path':'body.message','reason':'missing'}}),
                                ('500',{'error':{'code':'contract_response','path':'body.message','reason':'missing'}}),
                                ('503',{'error':{'code':'resource_limit'}})]:
                schema=dict(document['paths']['/api/test']['post']['responses'][status]['content']['application/json']['schema'],components=document['components'])
                validator=Draft202012Validator(schema)
                self.assertTrue(validator.is_valid({'message':'business error'}))
                self.assertTrue(validator.is_valid(body))
                self.assertFalse(validator.is_valid({'error':{'code':'invented'}}))

    def test_standard_subset_fixed_answers(self):
        with compiled('(shape) Input {s:(String); b:(Bool); n:(Null); a:(Array); m:(Map); d:(String):="default";}') as bundle:
            document=openapi(bundle[1],bundle[2],bundle[3])
            schema=document['components']['schemas']['S1_Input']
            Draft202012Validator.check_schema(schema)
            validator=Draft202012Validator(schema)
            valid={'s':'x','b':True,'n':None,'a':[1,'a',False,None,{}],'m':{'any':[True]}}
            cases=[(valid,True),(dict(valid,d='supplied'),True),
                   ({k:v for k,v in valid.items() if k!='n'},False),
                   (dict(valid,s=None),False),(dict(valid,b=1),False),
                   (dict(valid,a={}),False),(dict(valid,m=[]),False),(dict(valid,unknown=1),False)]
            for payload,expected in cases:
                with self.subTest(payload=payload):
                    self.assertEqual(validator.is_valid(payload),expected)
                    if expected:
                        self.assertEqual(invoke(bundle,payload),dict(payload,d=payload.get('d','default')))
                        self.assertNotIn('d',valid) # Validator never filled defaults.
                    else:
                        with self.assertRaises(ContractViolation):invoke(bundle,payload)

    def test_documented_numeric_difference(self):
        with compiled('(shape) Input {n:(Int); f:(Float);}') as bundle:
            schema=openapi(bundle[1],bundle[2],bundle[3])['components']['schemas']['S1_Input']
            Draft202012Validator.check_schema(schema)
            validator=Draft202012Validator(schema)
            for value in [{'n':1.0,'f':2.5},{'n':1,'f':2}]:
                self.assertTrue(validator.is_valid(value))
                with self.assertRaises(ContractViolation):invoke(bundle,value)
            for value in [{'n':True,'f':2.5},{'n':9007199254740992,'f':2.5},{'n':1.5,'f':2.5}]:
                self.assertFalse(validator.is_valid(value))
            self.assertTrue(validator.is_valid({'n':1,'f':2.5}))
            self.assertEqual(invoke(bundle,{'n':1,'f':2.5}),{'n':1,'f':2.5})

    def test_nested_reference_resolution(self):
        with compiled('(shape) Child {s:(String);}(shape) Input {child:Child;}') as bundle:
            document=openapi(bundle[1],bundle[2],bundle[3])
            schema={'$ref':'#/components/schemas/S2_Input','components':document['components']}
            Draft202012Validator.check_schema(schema)
            validator=Draft202012Validator(schema)
            self.assertTrue(validator.is_valid({'child':{'s':'ok'}}))
            self.assertFalse(validator.is_valid({'child':{'s':1}}))
            self.assertFalse(validator.is_valid({'child':{}}))


if __name__=='__main__':unittest.main()
