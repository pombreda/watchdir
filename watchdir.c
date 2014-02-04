#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/inotify.h>
#include <sys/select.h>
#include <linux/limits.h>

#define EVENT_SIZE  ( sizeof (struct inotify_event) )
#define EVENT_BUF_LEN     ( 1024 * ( EVENT_SIZE + 16 ) )
#define CMD_BUF_LEN 4096

#define CMD_QUIT 0
#define CMD_ADD 1
#define CMD_RM 2

int debug=0;

struct cmd {
	int code;
	char path[PATH_MAX];	/* add */
	uint32_t mask;		/* add */
	uint32_t wd;		/* rm */
};

void cmd_zero(struct cmd *cmdp) 
{
	cmdp->code=-1;
	bzero(cmdp->path, PATH_MAX);
	cmdp->mask=0;
	cmdp->wd=0;
}

void cmd_dump(struct cmd *cmdp) 
{
	/* xx code-dependent presentation.. */
	printf("cmd: code=%d path='%s' mask= %d wd=%u\n", 
	       cmdp->code, cmdp->path, cmdp->mask, cmdp->wd);
}
/** command parser
 * command syntax: <cmd-name> <arg> [<arg>]\n
 *    tokens are (single) space-separated
 *    note: the syntax is space sensitive; there should be no leading nor tailing spaces
 *          and tokens must be separated by exactly one space.
 * cmd spec
 *    todo..
 * example
 *    add x.dir 768
 *    rm 1
 *    quit
 */
int read_cmd(int fd, struct cmd *cmdp) 
{
	char buf[CMD_BUF_LEN];
	char *cmd_tok;
	int length;

	length = read(fd, buf, CMD_BUF_LEN-1); 
	buf[length]='\0';
	if (debug)
		printf("debug: read %d %s", length, buf);
	if (length==0) {
		/* termination command */
		cmdp->code=CMD_QUIT;
		return 0;
	} else if ( length < 0 ) {
		perror( "read" );
		return -1;
	}

	cmd_tok=strtok(buf, " ");
	if (debug)
		fprintf(stderr, "debug: op=%s\n", cmd_tok);
	if (cmd_tok==NULL) {
		fprintf(stderr, "warn: got null token\n"); /* ?? */
	} else if (strncmp(cmd_tok, "quit", strlen("quit"))==0) {
		cmdp->code=CMD_QUIT;
	} else if (strcmp(cmd_tok, "add")==0) { 
		/* add-watch: add <path> <mask> */
		char *t1, *t2;

		cmdp->code=CMD_ADD;

		t1=strtok(NULL, " ");
		assert(t1);
		strncpy(cmdp->path, t1, PATH_MAX);
		// cmdp->path=strdup(t1);

		t2=strtok(NULL, " ");
		assert(t2);
		sscanf(t2, "%d", &cmdp->mask);

	} else if (strcmp(cmd_tok, "rm")==0) { 
		/* rm-watch: rm <wd> */
		char *t;

		cmdp->code=CMD_RM;

		t=strtok(NULL, " ");
		assert(t);
		sscanf(t, "%d", &cmdp->wd);

	} else {
		printf("unknown cmd %s\n", cmd_tok);
		return -1;
	}

	return 0;
}

void report(struct inotify_event *event)
{
	printf("{ \"type\": \"event\", \"wd\": %u, \"path\": \"%s\", \"mask\": %u"
	       //", \"len\": %u"
	       " }\n", 
	       event->wd, 
	       event->len ? event->name : "",
	       event->mask
	       //, event->len
		);
	fflush(stdout);
}

int read_ino(int fd)
{
	char buffer[EVENT_BUF_LEN];
	int length=0;
	int i=0;

	bzero(buffer, EVENT_BUF_LEN);

	length = read( fd, buffer, EVENT_BUF_LEN ); 
	if ( length < 0 ) {
		perror( "read" );
		return length;	/* what to do. quit? */
	}  

	while (i<length) {
		struct inotify_event *event = (struct inotify_event *) &buffer[i];     
		report(event);
		i += EVENT_SIZE + event->len;
	}
	return 0;
}

int cmd_execute(struct cmd *cmdp, int ino_fd)
{
	int status=-1;

	/* todo: use dispatch (oo) */
	if (cmdp->code==CMD_ADD) {

		uint32_t wd=inotify_add_watch(ino_fd,cmdp->path,cmdp->mask);
		if (wd<0) {
			perror("inotify_add_watch");
			status=wd;
		} else {
			printf("{ \"type\": \"status\", "
			       "\"op\": \"add\", "
			       "\"arg\": {"
			       "\"path\": \"%s\", "
			       "\"mask\": %u "
			       "}, "
			       "\"wd\": %u "
			       "}\n", 
			       cmdp->path, 
			       cmdp->mask, 
			       wd);
			status=0;
		}

	} else if (cmdp->code==CMD_RM) {

		int s=inotify_rm_watch(ino_fd, cmdp->wd);
		/* replay */
		
		if (s<0) {
			perror("inotify_rm_watch");
			status=s;
		} else {
			printf("{ "
			       "\"type\": \"rm\", "
			       "\"wd\": %u, "
			       "\"status\": %d "
			       "}\n",
			       cmdp->wd, s);
			status=0;
		}
	} else {
		fprintf(stderr, "error: unkown code %d\n", cmdp->code);
		status=-1;
	}

	return status;
}


int main(int argc, const char* argv[])
{
	int read_fds[]={0,-1};
	fd_set read_fdset;
	int i;

	read_fds[1]=inotify_init();
	if (debug)
		fprintf(stderr, "debug: ino_fd %d\n", read_fds[1]);
	if ( read_fds[1] < 0 ) {
		perror( "inotify_init" );
	}

	for (;;) {
		int r;
		int maxfdplus=-1;

		FD_ZERO(&read_fdset);
		for (i=0; i<2; i++) {
			FD_SET(read_fds[i], &read_fdset);
			if (maxfdplus<read_fds[i]+1) {
				maxfdplus=read_fds[i]+1;
			}
		}

		r=select(maxfdplus, &read_fdset, NULL, NULL, NULL);

		if (debug) {
			for (i=0; i<2; i++) {
				if (FD_ISSET(read_fds[i], &read_fdset)) {
					fprintf(stderr, "debug: fd_isset=%d\n", read_fds[i]);
				}
			}
		}

		if (r<0) {
			perror("select");
		} else if (r==0) { /* timeout */
			fprintf(stderr, "timeout\n");
		} else {	/* r>0 */
			if (FD_ISSET(0, &read_fdset)) { /* xx use struct to dispatch */
				struct cmd cmd;
				
				cmd_zero(&cmd);
				read_cmd(0, &cmd);
				if (debug)
					cmd_dump(&cmd);
				if (cmd.code==CMD_QUIT) {
					break;
				} else {
					/* 
					 * xxx perhaps commands should not be executed here 
					 * in the handler.  may be the info should be saved
					 * and written when ino_fd is writable.
					 * there is a race where commands a lost 
					 * when they come in rapid succession..
					 */
					int s=cmd_execute(&cmd, read_fds[1]);
					if (s<0) {
						fprintf(stderr, "error: executing cmd");
					}
				}
	
			} else if (FD_ISSET(read_fds[1], &read_fdset)) {
				read_ino(read_fds[1]);
			}
		}
	}
	return 0;
}
