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

#define CMD_DONE 0
#define CMD_ADD 1
#define CMD_RM 2

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
	printf("cmd: %d '%s' %d\n", cmdp->code, cmdp->path, cmdp->mask);
}

int read_cmd(int fd, struct cmd *cmdp) 
{
	char buf[CMD_BUF_LEN];
	char *cmd_tok;
	int length;

	length = read(fd, buf, CMD_BUF_LEN-1); 
	buf[length]='\0';
	/* printf("read %d %s", length, buf); */
	if (length==0) {
		/* termination command */
		cmdp->code=CMD_DONE;
		return 0;
	} else if ( length < 0 ) {
		perror( "read" );
		return -1;
	}

	cmd_tok=strtok(buf, " ");
	if (cmd_tok==NULL) {
				/* done */
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

int read_ino(int fd)
{
	return 0;
}

int main(int argc, const char* argv[])
{
	int read_fds[]={0,-1};
	fd_set read_fdset;
	int i;

	read_fds[1]=inotify_init();
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
		if (r<0) {
			perror("select");
		} else if (r==0) { /* timeout */
		} else {	/* r>0 */
			if (FD_ISSET(0, &read_fdset)) { /* xx use struct to dispatch */
				struct cmd cmd;
				
				cmd_zero(&cmd);
				read_cmd(0, &cmd);
				/* cmd_dump(&cmd); */
				if (cmd.code==CMD_DONE) {
					break;
				} else if (cmd.code==CMD_ADD) {

					uint32_t wd=inotify_add_watch(read_fds[1],cmd.path,cmd.mask);
					/* reply */
					printf("add %s %u=%u\n", cmd.path, cmd.mask, wd);

				} else if (cmd.code==CMD_RM) {

					int s=inotify_rm_watch(read_fds[1], cmd.wd);
					/* replay */
					printf("rm %u=%d\n", cmd.wd, s);
					if (s<0) {
						perror("inotify_rm_watch");
					}
				}
	
			} else if (FD_ISSET(read_fds[1], &read_fdset)) {
				read_ino(read_fds[1]);
			}
		}
	}
	return 0;
}
