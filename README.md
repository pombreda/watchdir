watchdir
========

Watch directories for filesystem events. It's an inotify command for unix pipe.
Filesystem events are streamed to stdout for other programs to process.

* usage

        watchdir <dirs> -for <events>, 
        where <events> are inotify IN_* flags defined in inotify.h

* example

        watchdir /var/log/ -for create delete

* example run

        + ./watchdir /tmp -for create delete 
        watching /tmp for CREATE|DELETE
        + touch /tmp/foo
        CREATE	/tmp/foo
        + rm /tmp/foo
        DELETE	/tmp/foo
        + mkdir /tmp/bar
        CREATE,ISDIR	/tmp/bar
        + rmdir /tmp/bar
        DELETE,ISDIR	/tmp/bar
