import os
import time

for aid in ['zeus-agent-T-036-A', 'zeus-agent-T-036-D']:
    tid = aid.replace('zeus-agent-', '')
    stdout = os.path.join('.zeus/v2/agent-workspaces', aid, tid + '-stdout.txt')
    events = os.path.join('.zeus/v2/agent-workspaces', aid, '.zeus', 'v2', 'agent-logs', 'wave--1-events.jsonl')
    print('===', aid, '===')
    if os.path.exists(stdout):
        stat = os.stat(stdout)
        print('stdout size=', stat.st_size, 'mtime=', time.strftime('%H:%M:%S', time.localtime(stat.st_mtime)))
    if os.path.exists(events):
        with open(events, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines[-5:]:
            print(' ', line.strip())
    print()
