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

class File(object):
    """struct to hold path and file object"""

    def __init__(self, path, seek=None, open=True):

        self.path=path
        self.seek=seek
        if open:
            self.fh=file(path, 'r')
            if seek:
                self.fh.seek(0, seek)
            print self

    def __repr__(self):
        return 'File(%s, %s)' % (self.path, self.seek)
    
    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        return self.path==other.path

    def fileno(self):
        return self.fh.fileno()

# need a str version of '\t', '\n', ' ' to operate on byte string lines.
HT,LF,SP=[c.encode('utf8') for c in ['\t', '\n', ' ']]

@baker.command
def tailall():

    files=set()

    while True:
        # read from the controll channel
        line=sys.stdin.readline()
        if not line:
            break

        # add new files to watch
        event=json.loads(line)
        flags=event.get('flags',[])
        path=event.get('path')
        if not path:
            pass
        elif 'CLOSE_WRITE' in flags:
            print >>sys.stderr, 'remove:', path # xx not getting called?
            files.discard(File(path, open=False))
        elif File(path, open=False) in files:
            pass
        elif 'MODIFY' in flags:
            files.add(File(path, seek=2))
        elif 'OPEN' in flags:
            files.add(File(path))

        # drain each file on which activities have been detected
        for logfile in files:
            while True:
                line=logfile.fh.readline()
                if not line:
                    break
                # taillall output
                print HT.join([logfile.path.encode('utf8'), line.strip(LF).replace(HT, SP)])
                

def ints(start=0):
    i=start
    while True:
        yield i
        i+=1

@baker.command
def writer(iterations=10, label=None, chunk=10, line=500, sleep=1, out=None, flush=False, debug=False):
    """log writer for testing"""

    import random

    if not label:
        label=str(os.getpid())
    
    if out:
        outfile=file(out, 'w')
    else:
        outfile=sys.stdout

    n=0
    
    for i in ints():
        if i>=iterations:
            break
        # print some lines
        cs=random.randrange(0,chunk)
        for j in range(cs):
            # each with some length
            length=random.randrange(0,line)
            outline=' '.join(map(str,[label, n, '.' * length, '$']))
            print >>outfile, outline
            if flush:
                outfile.flush()
            if debug:
                print >>sys.stderr, outline
                sys.stderr.flush()
            n+=1
        # sleep some
        time.sleep(random.random()*sleep)
    


baker.run()
