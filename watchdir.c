#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/inotify.h>

/**
   based on ...
 */

#define EVENT_SIZE  ( sizeof (struct inotify_event) )
#define EVENT_BUF_LEN     ( 1024 * ( EVENT_SIZE + 16 ) )

struct event_type {
	const char *name;
	int mask;
	const char *desc;
};

struct event_type event_types[]={
	{ "ACCESS", 		0x00000001,	"File was accessed" },
	{ "MODIFY", 		0x00000002,	"File was modified" },
	{ "ATTRIB", 		0x00000004,	"Metadata changed" },
	{ "CLOSE_WRITE", 	0x00000008,	"Writtable file was closed" },
	{ "CLOSE_NOWRITE", 	0x00000010,	"Unwrittable file closed" },
	{ "OPEN", 		0x00000020,	"File was opened" },
	{ "MOVED_FROM", 	0x00000040,	"File was moved from X" },
	{ "MOVED_TO", 		0x00000080,	"File was moved to Y" },
	{ "CREATE", 		0x00000100,	"Subfile was created" },
	{ "DELETE", 		0x00000200,	"Subfile was deleted" },
	{ "DELETE_SELF", 	0x00000400,	"Self was deleted" },
	{ "MOVE_SELF", 		0x00000800,	"Self was moved" },
};

struct event_type modifier_types[]={
	/* test the most likely ones first. */
	{ "ISDIR",		0x40000000,	"event occurred against dir" },

	/* the following are legal events.  they are sent as needed to any watch */
	{ "UNMOUNT",		0x00002000,	"Backing fs was unmounted" },
	{ "Q_OVERFLOW",		0x00004000,	"Event queued overflowed" },
	{ "IGNORED",		0x00008000,	"File was ignored" },

	/* helper events 
	 * { "CLOSE",		(IN_CLOSE_WRITE, | IN_CLOSE_NOWRITE) "close" },
	 * { "MOVE",		(IN_MOVED_FROM, | IN_MOVED_TO) "moves" },
	 */

	/* special flags */
	{ "ONLYDIR",		0x01000000,	"only watch the path if it is a directory" },
	{ "DONT_FOLLOW",	0x02000000,	"don't follow a sym link" },
	{ "MASK_ADD",		0x20000000,	"add to the mask of an already existing watch" },
	{ "ONESHOT",		0x80000000,	"only send event once" },

	};

int num_event_types=sizeof(event_types)/sizeof(struct event_type);
int num_modifier_types=sizeof(modifier_types)/sizeof(struct event_type);

void dump_event(struct inotify_event *e, const char *msg) 
{
	if (msg==NULL) {
		msg="";
	}
	fprintf(stderr, "event: %s %d %s\n", msg, e->wd, e->name);
}

struct dir {
	const char *path;
	int wd;
};

struct opts {
	int mask;

	struct dir *dirv;
	int dirc;

	struct event_type **event_typev;
	int event_typec;
};

/* 
   parse 
   $0 dir1 dir2 ... -f flg1 flg2 ...
   Directories get written to the dirv arg.
   Mask is returned.
 */
struct opts opts_init(int argc, const char* argv[]) 
{
	struct opts opts;

	opts.mask=0;
	opts.dirv=malloc(sizeof(struct dir)*argc) ;
	opts.event_typev=malloc(sizeof(struct event_type)*num_event_types);

	const char *sep="-f";
	int i=0;
	int j=0;
	int l=0;

	i++;			/* lose program name */
	for (; i<argc; i++) {
		if (strncmp(argv[i], sep, strlen(sep))==0) {
			break;
		}
		opts.dirv[j].path=argv[i];
		opts.dirv[j].wd=0;
		j++;
	}
	opts.dirc=j;
	i++;			/* lose the sep */
	for (; i<argc; i++) {
		int k;
		struct event_type *matching_event=NULL;

		for (k=0; k<num_event_types; k++) {
			if (strcasecmp(argv[i], event_types[k].name)==0) {
				matching_event=&event_types[k];
				break;
			}
		}
		if (matching_event) {
			opts.event_typev[l++]=matching_event;
			assert(l<num_event_types); /* should not happen unless repeated.. */
			opts.mask|=matching_event->mask;
		} else {
			fprintf(stderr, "ignoring unknown event '%s'\n", argv[i]);
		}
	}
	opts.event_typec=l;
	return opts;
}

void opts_finish(struct opts* opts) 
{
	free(opts->dirv);
	opts->dirv=NULL;
	free(opts->event_typev);
	opts->event_typev=NULL;
}

void report(struct inotify_event *event, struct opts *opts)
{
	int i;
	int event_mask=event->mask;
	const char *dir_path=NULL;

	/* 
	 * find the dir 
	 */
	for (i=0; i<opts->dirc; i++) {
		if (opts->dirv[i].wd==event->wd) {
			dir_path=opts->dirv[i].path;
			break;
		}
	}

	/* 
	 * find the matching event type.
	 */
	for (i=0; i<opts->event_typec && event_mask; i++) {
		struct event_type *et=opts->event_typev[i];

		if (event_mask & et->mask) {
			printf("%s", et->name);
			event_mask &= ~et->mask;
			break;	/* at most one event type should match */
		}
	}
	/* 
	 * if there are bits left, scan for non-event (modifier) flags.
	 */
	for (i=0; i<num_modifier_types && event_mask; i++) {
		struct event_type *modifier=&modifier_types[i];
		if (event_mask & modifier->mask) {
			printf(",%s", modifier->name);
			event_mask &= ~modifier->mask;
		}
	}

	printf("\t%s%s%s\n", 
	       dir_path, 
	       dir_path[strlen(dir_path)-1]=='/' ? "" : "/", 
	       event->name);
	fflush(stdout);
}

int main(int argc, const char* argv[])
{
	int fd;
	int j;
	struct opts opts;

	opts=opts_init(argc, argv);

	if (opts.dirc<=0 || opts.event_typec<=0) {
		fprintf(stderr, "usage: %s dir1 dir2 .. -for create delete ..\n", argv[0]);
		return 1;
	}

	fd = inotify_init();
	if ( fd < 0 ) {
		perror( "inotify_init" );
	}

	fprintf(stderr, "watching ");
	for (j=0; j<opts.dirc; j++) {
		opts.dirv[j].wd = inotify_add_watch( fd, opts.dirv[j].path, opts.mask );
		fprintf(stderr, "%s ", opts.dirv[j].path);
	}
	fprintf(stderr, "for ");
	for (j=0; j<opts.event_typec; j++) {
		if (opts.mask & opts.event_typev[j]->mask) {
			fprintf(stderr, "%s%s", j>0 ? "|" : "", opts.event_typev[j]->name);
		}
	}
	fprintf(stderr, "\n");

	for(;;) {
		char buffer[EVENT_BUF_LEN];
		int length=0;
		int i=0;

		length = read( fd, buffer, EVENT_BUF_LEN ); 
		if ( length < 0 ) {
			perror( "read" );
		}  

		while (i<length) {
			struct inotify_event *event = (struct inotify_event *) &buffer[i];     
			if (event->len>0) {
				report(event, &opts);
				i += EVENT_SIZE + event->len;
			}
		}
	}
	/* 
	 * clean up
	 */
	for (j=0; j<opts.dirc; j++) {
		inotify_rm_watch(fd, opts.dirv[j].wd);
	}
	opts_finish(&opts);
	close( fd );
}
