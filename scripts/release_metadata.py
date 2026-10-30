"""Validate a release tag before building or publishing anything."""
import argparse
import os
from pathlib import Path
import re


def validate(root, tag, repository):
    if not re.fullmatch(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', tag):
        raise ValueError('Release tags must use vMAJOR.MINOR.PATCH, without prerelease suffixes.')
    config=(root/'ha_ai_studio/config.yaml').read_text()
    def field(name):
        match=re.search(r'^'+name+r':\s*([^\n]+)$',config,re.MULTILINE)
        if not match:raise ValueError('Missing app metadata: '+name)
        return match[1].strip().strip('"\'')
    version=tag[1:]
    if field('version')!=version:raise ValueError('Tag and config.yaml version must match.')
    if field('arch')!='[amd64]':raise ValueError('Only the tested amd64 architecture can be released.')
    image=field('image')
    if image!='ghcr.io/'+repository.lower():raise ValueError('Image must match the publishing repository.')
    discovery=(root/'ha_ai_studio/app/discovery.py').read_text()
    match=re.search(r'^VERSION = [\'"]([^\'"]+)[\'"]$',discovery,re.MULTILINE)
    if not match or match[1]!=version:raise ValueError('Discovery version must match the release.')
    return {'version':version,'image':image,'target':image+':'+version}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tag',required=True)
    parser.add_argument('--repository',required=True)
    args=parser.parse_args()
    try:result=validate(Path(__file__).resolve().parents[1],args.tag,args.repository)
    except ValueError as error:parser.exit(1,str(error)+'\n')
    output=''.join(f'{key}={value}\n' for key,value in result.items())
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as stream:stream.write(output)
    print(output,end='')
