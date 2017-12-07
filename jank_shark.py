import argparse
import atexit
import os
import sys
import subprocess
import tempfile

EXTRACT_SECRETS = "https://repo1.maven.org/maven2/name/neykov/extract-ssl-secrets/2.0.0/extract-ssl-secrets-2.0.0.jar"

FIFO_LOCATION = "/tmp/remote"
# DEV_PEM = os.environ['DEV_PEM']
# DMZ_PEM = os.environ['DMZ_PEM']
# PEM_FILE_LOCATION = DEV_PEM
REMOTE_INTERFACE = "eth0"

PROCESSES = []
def cleanup_subprocesses():
    for process in PROCESSES:
        process.kill()
atexit.register(cleanup_subprocesses)

# Flags
parser = argparse.ArgumentParser()
parser.add_argument("-host", help="host to intercept traffic of", required=True)
parser.add_argument("-f", "--fifo_loc", help="location for fifo packet queue", default="/tmp/remote_fifo")
parser.add_argument("-l", "--interface", help="name of remote interface to intercept", default="eth0")
parser.add_argument("-t", "--tomcat", help="wire up extract-ssl-secrets for tomcat", action="store_true")

group = parser.add_mutually_exclusive_group()
group.add_argument("--pem_dmz", action="store_true")
group.add_argument("--pem_dev", action="store_true")
group.add_argument("--pem")

args = parser.parse_args()
print(args)

# Check out flags
pem_filename = ""
if args.pem_dev:
    if not "DEV_PEM" in os.environ:
        sys.exit("pem_dev flag used but $DEV_PEM is not set")
    else:
        pem_filename = os.environ['DEV_PEM']

if args.pem_dmz:
    if not "DMZ_PEM" in os.environ:
        sys.exit("pem_dmz flag used but $DMZ_PEM is not set")
    else:
        pem_filename = os.environ['DMZ_PEM']

if args.pem:
    pem_filename = args.pem

# Establish packet fifo
tmpdir = tempfile.mkdtemp()
filename = os.path.join(tmpdir, 'fifo')

try:
    os.mkfifo(filename)
except OSError as e:
    sys.exit("Failed to create FIFO: %s".format(e))

# Open new FIFO
print("FIFO location: {}".format(filename))

# Start up Wireshark
wireshark_command = ["wireshark", "-k", "-i", "{}".format(filename)]
wireshark_cmd = subprocess.Popen(wireshark_command,
                                 shell=False,
                                 stdout=subprocess.PIPE,
                                 stdin=subprocess.PIPE)
PROCESSES.append(wireshark_cmd)

# Connect to host and stream tcp
output_fifo = open(filename, 'w')
fifo_redirect_command = "sudo tcpdump -s 0 -U -n -w - -i {} not port 22".format(args.interface)
fifo_ssh_cmd = subprocess.Popen(["ssh", "-i", "{}".format(pem_filename), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "ubuntu@{}".format(args.host), '{}'.format(fifo_redirect_command)],
                            shell=False,
                            stdout=output_fifo,
                            stdin=subprocess.PIPE)
PROCESSES.append(fifo_ssh_cmd)

wireshark_cmd.wait()


