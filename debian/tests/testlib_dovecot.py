#!/usr/bin/python3
'''
    Packages required: dovecot-imapd dovecot-pop3d
'''

import subprocess, shutil, grp, os, os.path, sys, time

class Dovecot:
    def get_mailbox(self):
        return self.mailbox

    def __init__(self,user,config=None):
        '''Create test scenario.

        dovecot is configured for all protocols (imap[s] and pop3[s]), a test
        user is set up, and /var/mail/$user contains an unread and a read mail.
        '''

        self.old_version = False
        if config == None:
                config='''
protocols = imap pop3
log_timestamp = "%Y-%m-%d %H:%M:%S "
mail_privileged_group = mail
managesieve_notify_capability = mailto
managesieve_sieve_capability = fileinto reject envelope encoded-character vacation subaddress comparator-i;ascii-numeric relational regex imap4flags copy include variables body enotify environment mailbox date index ihave duplicate mime foreverypart extracttext
mmap_disable = yes
ssl = yes
ssl_cert = </etc/dovecot/dovecot.pem
ssl_key = </etc/dovecot/private/dovecot.pem
auth_mechanisms = PLAIN
mail_location = mbox:~/mail:INBOX=/var/mail/%u
service auth {
  user = root
}
protocol pop3 {
  pop3_uidl_format = %08Xu%08Xv
}
userdb {
  driver = passwd
}
passdb {
  driver = passwd-file
  args = username_format=%n scheme=PLAIN /etc/dovecot/test.passwd
}
'''

        # make sure that /etc/inetd.conf exists to avoid init script errors
        self.created_inetdconf = False
        if not os.path.exists('/etc/inetd.conf'):
            open('/etc/inetd.conf', 'a').close()
            self.created_inetdconf = True

        # configure and restart dovecot
        if not os.path.exists('/etc/dovecot/dovecot.conf.autotest'):
            shutil.copyfile('/etc/dovecot/dovecot.conf', '/etc/dovecot/dovecot.conf.autotest')
        with open('/etc/dovecot/dovecot.conf', 'w') as cfgfile:
            cfgfile.write(config)

        with open('/etc/dovecot/test.passwd','w') as f:
            f.write('%s:{plain}%s\n' % (user.login, user.password))

        # restart will fail if dovecot is not already running
        subprocess.call(['service', 'dovecot', 'stop'], stdout=subprocess.PIPE)
        # systemd rate limit will kill it without a bit of sleep (max 5 in 10 sec)
        time.sleep(3)
        subprocess.check_call(['service', 'dovecot', 'start'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.running = True

        # create test mailbox with one new and one old mail
        self.mailbox = '/var/mail/' + user.login
        self.orig_mbox = \
'''From test1@test1.com Fri Nov 17 02:21:08 2006
Date: Thu, 16 Nov 2006 17:12:23 -0800
From: Test User 1 <test1@test1.com>
To: Dovecot tester <dovecot@test.com>
Subject: Test 1
Status: N

Some really important news.

From test2@test1.com Tue Nov 28 11:29:34 2006
Date: Tue, 28 Nov 2006 11:29:34 +0100
From: Test User 2 <test2@test2.com>
To: Dovecot tester <dovecot@test.com>
Subject: Test 2
Status: R

More news.

Get cracking!
'''
        with open(self.mailbox, 'w') as f:
            f.write(self.orig_mbox)
        os.chown(self.mailbox, user.uid, grp.getgrnam('mail')[2])
        os.chmod(self.mailbox, 0o660)

    def __del__(self):
        if self.running:
            self.close()

    def close(self):
        assert self.running

        # restore original configuration and restart dovecot
        os.rename('/etc/dovecot/dovecot.conf.autotest', '/etc/dovecot/dovecot.conf')
        # quiesce, default configuration has no protocols
        subprocess.call(['service', 'dovecot', 'restart'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        if self.created_inetdconf:
            os.unlink('/etc/inetd.conf')

        self.running = False

    def get_ssl_fingerprint(self):
        pem = '/etc/ssl/certs/dovecot.pem'
        if not os.path.exists(pem):
            pem = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
        
        sp = subprocess.Popen(['openssl','x509','-in',pem,'-noout','-md5','-fingerprint'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
        return sp.communicate(None)[0].split('=',1)[1].strip()
        
