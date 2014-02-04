#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys,os
import time
import json
from subprocess import Popen, PIPE
from collections import namedtuple
import baker

Flag = namedtuple('Flag', 'name mask desc')

flags=[
    Flag( "ACCESS", 		0x00000001,	"File was accessed" ),
    Flag( "MODIFY", 		0x00000002,	"File was modified" ),
    Flag( "ATTRIB", 		0x00000004,	"Metadata changed" ),
    Flag( "CLOSE_WRITE", 	0x00000008,	"Writtable file was closed" ),
    Flag( "CLOSE_NOWRITE", 	0x00000010,	"Unwrittable file closed" ),
    Flag( "OPEN", 		0x00000020,	"File was opened" ),
    Flag( "MOVED_FROM", 	0x00000040,	"File was moved from X" ),
    Flag( "MOVED_TO", 		0x00000080,	"File was moved to Y" ),
    Flag( "CREATE", 		0x00000100,	"Subfile was created" ),
    Flag( "DELETE", 		0x00000200,	"Subfile was deleted" ),
    Flag( "DELETE_SELF", 	0x00000400,	"Self was deleted" ),
    Flag( "MOVE_SELF", 		0x00000800,	"Self was moved" ),
    Flag( "ISDIR",		0x40000000,	"event occurred against dir" ),
    Flag( "UNMOUNT",		0x00002000,	"Backing fs was unmounted" ),
    Flag( "Q_OVERFLOW",		0x00004000,	"Event queued overflowed" ),
    Flag( "IGNORED",		0x00008000,	"File was ignored" ),
]

# xx make it module scoped.
flagd=dict( (f.name, f) for f in flags )

class Struct(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)
FLAG=Struct(**flagd)

def mask_to_flags(mask):
    # todo:
    #   optimization: 
    #      * limit traversal to named flags only.
    #      * priotize by likelihood

    for f in flags:
        if mask & f.mask:
            yield f

@baker.command
def watch(root):

    mask=0
    for f in flags:
        mask|=f.mask

    engine_path=os.path.join(os.path.dirname(__file__), 'watchdir')
    engine=Popen([engine_path], stdin=PIPE, stdout=PIPE)

    dirs=[cur for cur,_,_ in os.walk(root)]
    for d in dirs:
        cmd='add {dir} {mask}\n'.format(dir=d, mask=mask)
        print >>sys.stderr, 'cmd:', cmd.strip('\n')
        sys.stderr.flush()
        engine.stdin.write(cmd)
        # xxx workaround for a race
        time.sleep(0.1)         

    wd_to_path={}

    def event_path(e):
        return os.path.join(wd_to_path[e['wd']], event['path'])

    while True:
        line=engine.stdout.readline()
        if not line:
            print 'done:'
            break

        try:
            event=json.loads(line)
        except ValueError, e:
            print >>sys.stderr, 'ERROR:', e, line
            sys.stderr.flush()
            continue

        typ=event['type']
        if typ=='status':
            # maintain wd-->dirpath mapping.
            # {"type": "status", "op": "add","arg": {"path":"x.dir/", "mask":1073803263 }, "wd":1}
            wd_to_path[event['wd']]=event['arg']['path']

        elif typ=='event':
            mask=event['mask']
            flgs=[f.name for f in mask_to_flags(mask)]
            event['flags']=flgs
            # if ["CREATE", "ISDIR"], then add this one as well
            if mask & FLAG.CREATE.mask and mask & FLAG.ISDIR.mask:
                # { "type": "event", "wd": 1, "path": "subdir", "mask": 1073742080 }
                #parent=wd_to_path[event['wd']]
                #dirpath=os.path.join(parent, event['path'])
                dirpath=event_path(event)
                cmd='add {dir} {mask}\n'.format(dir=dirpath, mask=mask)
                # xx use event format to report
                print >>sys.stderr, 'cmd:', cmd.strip('\n')
                sys.stderr.flush()
                engine.stdin.write(cmd)
            # ["DELETE", "ISDIR"]
            elif mask & FLAG.DELETE.mask:
                if mask & FLAG.ISDIR.mask:
                    # delete all of my records under this node
                    dirpath=event_path(event)
                    print >>sys.stderr, 'RMDIR:', dirpath
                    for wd,dp in wd_to_path.items():
                        if dp.startswith(dirpath):
                            print >>sys.stderr, '\tRM:', dp
                            del wd_to_path[wd]
            # DELETE_SELF. what does this mean exactly?
            elif mask & FLAG.DELETE.mask:
                pass

        print json.dumps(event)
        sys.stdout.flush()
        
    engine.wait()


baker.run()
