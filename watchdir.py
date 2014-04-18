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

def report_event(wd_to_path, event):

    event['time']=time.time()
    if event['type']=='event':
        report=dict(path=os.path.join(wd_to_path[event['wd']], event['path']),
                    flags=event['flags'],
                    time=event['time'],
                    wd=event['wd'],
        )
    else:
        report=event

    print json.dumps(report)



@baker.command
def watch(root):

    # xxx how should flags be passed in?
    mask=0
    for f in flags:
        if f.mask!=FLAG.ACCESS.mask: # xx
            mask|=f.mask

    engine_path=os.path.abspath(os.path.join(os.path.dirname(__file__), 'watchdir'))
    assert os.path.exists(engine_path), ('need', engine_path)
    try:
        engine=Popen([engine_path], stdin=PIPE, stdout=PIPE)
    except Exception, e:
        print >>sys.stderr, 'ERROR:', e, [engine_path]
        e.args+=(engine_path,)
        raise

    if root=='-':
        # read seed dirs from stdin
        dirs=[d.strip() for d in sys.stdin.readlines()]
    else:
        dirs=[cur for cur,_,_ in os.walk(root)]

    for d in dirs:
        cmd='add {dir} {mask}\n'.format(dir=d, mask=mask)
        print >>sys.stderr, json.dumps(['DEBUG', 'cmd', cmd.strip('\n')])
        sys.stderr.flush()
        engine.stdin.write(cmd)
        # xxx workaround for a race
        #time.sleep(0.05)         

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

            report_event(wd_to_path, event)

            # if ["CREATE", "ISDIR"], then add this one as well
            # xx are these conditons known to be multually exclusive?
            if mask & FLAG.CREATE.mask and mask & FLAG.ISDIR.mask:
                # { "type": "event", "wd": 1, "path": "subdir", "mask": 1073742080 }
                dirpath=event_path(event)
                cmd='add {dir} {mask}\n'.format(dir=dirpath, mask=mask)
                # xx use event format to report
                print >>sys.stderr, json.dumps(['DEBUG', 'cmd', cmd.strip('\n')])
                sys.stderr.flush()
                engine.stdin.write(cmd)
            # ["DELETE", "ISDIR"]
            elif mask & FLAG.DELETE.mask:
                if mask & FLAG.ISDIR.mask:
                    # delete all of my records under this node.
                    # xxx this might be overzealous; just wait for events of inferior dirs?
                    # should the engine be notified or does it take care of this?
                    dirpath=event_path(event)
                    print >>sys.stderr, json.dumps(['DEBUG', 'recursive rm', dirpath])
                    for wd,dp in wd_to_path.items():
                        if dp.startswith(dirpath):
                            print >>sys.stderr, json.dumps(['DEBUG', 'rmdir', (wd, dp)])
                            # might get events for the just-deleted dir, so this is premature.
                            # on the other hand, we might not receive delete events for subdir.
                            # so how to manage this?  just let the stale one be until it gets clobbered 
                            # by a new dir with the same id.
                            # del wd_to_path[wd]
            # DELETE_SELF. what does this mean exactly?
            elif mask & FLAG.DELETE.mask:
                pass

        sys.stdout.flush()
        
    engine.wait()


def modified():
    
    while True:
        line=sys.stdin.readline()
        if not line:
            break
        try:
            notice=json.loads(line)
        except ValueError, e:
            print >>sys.stderr, 'malformed event', [line], e
            continue
        if 'MODIFY' in notice.get('flags', []):
            yield (notice['path'], notice['time'])

FileInfo=namedtuple('FileInfo', 'fh timestamp error'.split())

@baker.command
def tailall(max_fh=20, gc_int=40):

    # need a str version of '\t', '\n', ' ' to operate on encoded (non-unicode) lines.
    HT,LF,SP=[c.encode('utf8') for c in ['\t', '\n', ' ']]
    assert isinstance(HT, str)

    try:
        import setproctitle
        setproctitle.setproctitle('tailall')
    except ImportError:
        pass

    path_to_fh={}

    for i,(path,_) in enumerate(modified()):
        
        fileinfo=path_to_fh.get(path)

        if not fileinfo:
            fh,err=None,None
            try:
                fh=file(path,'r')
                fh.seek(0,2)
            except IOError, err:
                print >>sys.stderr, json.dumps(['WARN', 'failed to open', [path, str(err)]])
                # remember to ignore this one since permission is unlikely to change..
            fileinfo=FileInfo(fh, time.time(), err)
            path_to_fh[path]=fileinfo

        assert fileinfo
        if fileinfo.error:        # presumably unrecoverable..
            print >>sys.stderr, json.dumps(['DEBUG', 'ignore bad file', (path, fileinfo.timestamp, repr(fileinfo.error))])
            continue

        for line in fh.readlines():
            try:
                # Compose output using bytestring operations, since the encoding of line
                # is unknown. If any of the operand is unicode, implicit conversion and encoding 
                # results, leading to error.
                print HT.join([path.encode('utf8'), line.strip(LF).replace(HT, SP)])
            except Exception, e:
                print >>sys.stderr, 'xx:', [e, line]
                raise
            sys.stdout.flush()

        # every so often, gc ones that have been inactive for a while
        # todo: heep
        if len(path_to_fh)>max_fh and i%40==0:
            items=path_to_fh.items() # [ (path,FileInfo), .. ]
            items.sort(key=lambda item: item[1].timestamp)
            for p,fi in items[:max_fh]:
                fi.fh.close()
                del path_to_fh[p]
                print >>sys.stderr, 'gc:', p, fi.timestamp
                sys.stderr.flush()

baker.run()
