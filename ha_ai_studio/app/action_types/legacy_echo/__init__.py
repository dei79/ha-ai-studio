"""Frozen compatibility runtime for saved Echo instances; new Echo comes from Git."""
import copy
from ...domain import Invalid

metadata = {'type':'echo','name':'Echo','description':'Return the supplied JSON data unchanged.',
    'input_schema':{'type':'object','required':['request_id','data'],'additionalProperties':False,
        'properties':{'request_id':{'type':'string','minLength':1,'maxLength':128},'data':{}}},
    'output_schema':{'type':'object','required':['request_id','status','data'],'additionalProperties':False,
        'properties':{'request_id':{'type':'string'},'status':{'const':'success'},'data':{}}},
    'example':{'request_id':'test-001','data':{'message':'Hello','value':42}}}

def validate(settings):
    if settings != {}:raise Invalid('Echo has no configurable settings.')
    return {}

def validate_input(message):
    if set(message)!={'request_id','data'}:raise Invalid('Provide exactly request_id and data.')

async def execute(data,settings):
    validate(settings)
    return copy.deepcopy(data)
