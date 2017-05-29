import socket
import sys

# Sets up the server's welcoming socket
def init_socket(port):
	ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	ssocket.bind(("", port))
	ssocket.listen(5)
	return ssocket

# Accepts a TCP connection from the welcoming socket
# and returns the connection socket.
def connect(ssocket):
	(csocket, caddress) = ssocket.accept()
	return csocket

# A class to hold the input string and keep track of the
# Parser's progress
class Iterator():
	def __init__(self, s):
		self.s = s
		self.a = 0
	def next(self):
		if self.a < len(self.s):
			out = self.s[self.a]
			self.a += 1
			return out
	def peek(self):
		if self.a < len(self.s):
			return self.s[self.a]
	def reset(self):
		self.a = 0

def isLetter(char):	# Determines if a char is a letter based on its ASCII value
	num = ord(char)   
	return (num >= 65 and num<=90) or (num>=97 and num<=122)

def isNumber(char):	# Determines if a char is a number based on ASCII value
	num = ord(char)
	return (num>=48 and num<=57)

# Tests for the words "MAIL FROM:" accounting for whitespace and nullspace
def literalMailFrom(i):
	for c in "MAIL":
		if c != i.next():
			return "ERROR -- mail-from-cmd"
	if i.peek() != " ":
		return "ERROR -- mail-from-cmd"
	while(i.peek() == " " or i.peek() == "	"):
		i.next()
	for c in "FROM:":
		if c != i.next():
			return "ERROR -- mail-from-cmd"

# Root test test method for mail-from-cmd parser
def testMailFrom(i): 
	error = literalMailFrom(i)
	if error is not None:
		return error
	error = nullPathNull(i)
	if error is not None:
		return "ERROR -- mail-from-cmd"

# Checks to see if the path portion of mailfrom and rcpt-to grammars
# is surrounded by vaild nullspace
def nullPathNull(i):
	while(i.peek() == " " or i.peek() == "	"):
		i.next()
	error = pathtest(i)
	if error is not None:
		return error
	while i.peek() is not None and i.peek() != "":
		if i.peek() != " " and i.peek() != "	":
			return "ERROR"
		i.next() 

# Tests for errors in the <path> grammar. Calls the error-checking function for
# the mailbox sub-grammar. 
def pathtest(i):
	if i.next() != "<":
		return "ERROR -- path"
	error = mailboxtest(i)
	if error is not None:
		return error
	if i.next() != ">":
		return "ERROR -- path"

# Tests for errors in the <mailbox> grammar. Calls and handles errors for the
# <local-part> and <domain> sub grammars.
def mailboxtest(i):
	error = localtest(i)
	if error is not None:
		return error
	if i.next() != "@":
		return "ERROR -- mailbox"
	error = domaintest(i)
	if error is not None:
		return error

# Tests for errors in the <local-part> grammar.
def localtest(i):
	special = [ "<" , ">" , "(" , ")" , "[" , "]" , "\\" , "." , "," , ";" , ":" , "@" , "\"","	"," " ]
	count = 0
	while not(i.peek() in special or i.peek() is None or ord(i.peek()) >= 128):
		count += 1
		i.next()
	if count < 1:
		return "ERROR -- local-part"

# Tests for errors in the <domain> grammar.
def domaintest(i):
	count = 0
	if i.peek() == "@" or i.peek() is None or not isLetter(i.peek()):
		return "ERROR -- domain"
	while i.peek() is not None and (isNumber(i.peek()) or isLetter(i.peek()) or i.peek() == "."):
		s = i.next()
		count += 1
		if s == ".":
			if not isLetter(i.peek()) or count <= 2:
				return "ERROR -- domain"
			count = 0
	if count < 2:
		return "ERROR -- domain"

# Tests for vaild rcpt-to-cmd grammar accounting for nullspace
# and whitespace
def literalRcptTo(i):
	for c in "RCPT":
		if c != i.next():
			return "ERROR"
	if i.peek() != " ":
		return "ERROR"
	while(i.peek() == " " or i.peek() == "	"):
		i.next()
	for c in "TO:":
		if c != i.next():
			return "ERROR"
			
# Root test method for RCPT TO cmd parser
def testRcptTo(i):
	error = literalRcptTo(i)
	if error is not None:
		return error
	error = nullPathNull(i)
	if error is not None:
		return error

# Test for valid DATA cmd grammar.
def testData(i):
	for c in "DATA":
		if c != i.next():
			return "ERROR"
	while i.peek() is not None and i.peek() != "":
		if i.peek() != " " and i.peek() != "	":
			return "ERROR"
		i.next()

# Tests for errors in the HELO command
def testHelo(i):
	for c in "HELO":
		if c != i.next():
			return "ERROR"
	while i.peek() == " " or i.peek() == "	":
		i.next()
	error = domaintest(i)
	if error is not None:
		return error
	while i.peek() is not None:
		if i.next() not in [" ","	"]:
			return "ERROR"


def main():
	pError = "501 Syntax error in parameters or arguments\n"
	bsError = "503 Bad sequence of commands\n"
	cmdOk = "250 OK\n"
	try:
		port = int(sys.argv[1])
	except:
		print "Bad arguments"
		exit()
	try:
		ssocket = init_socket(port)
	except:
		print "Fatal network error -- cannot establish host socket"
		exit()
	csocket = None
	connected = False
	state = 0
	recips = []
	sender = ""
	message = ""

	while True: #main input loop
		try:
			if not connected:
				csocket = connect(ssocket)
				csocket.sendall("220 " + socket.gethostname()+"\n")
				connected = True
			else:
				if state != 4: line = csocket.recv(4096).replace("\n","").replace("\x0d","")
				#print line
				#print ord(line[len(line)-1])
				if line.strip() == "QUIT":
					csocket.close()
					connected = False
					continue
				if literalRcptTo(Iterator(line)) is not None and literalMailFrom(Iterator(line)) is not None \
				and line[:5] not in ["DATA","DATA ","DATA\n"] and state != 4 and line[:5] not in ["HELO","HELO ","HELO\n"]:
					csocket.sendall("500 Syntax error: command unrecognized\n")
					continue
				
				# This if-elif structure is a state machine. Each clause represents a vaild
				# state, and the if structures nested within each clause represent that state's
				# adjacencies.
				if state == 0:
					if line[:4] == "HELO":
						if testHelo(Iterator(line)) is None:
							csocket.sendall("250 Hello " + line[4:].strip() + "! Pleased to meet you.\n")
							state += 1
						else:
							csocket.sendall(pError)
					else:
						csocket.sendall(bsError)
				elif state == 1:
					if literalMailFrom(Iterator(line)) is None:
						if testMailFrom(Iterator(line)) is None:
							sender = line[line.find("<")+1:line.find(">")]
							csocket.sendall(cmdOk)
							state+=1;
						else:
							csocket.sendall(pError)
					else:
						csocket.sendall(bsError)
				elif state == 2:
					if literalRcptTo(Iterator(line)) is None:
						if testRcptTo(Iterator(line)) is None:
							recips.append(line[line.find("<")+1:line.find(">")])
							csocket.sendall(cmdOk)
							state+=1;
						else:
							csocket.sendall(pError)
					else:
						csocket.sendall(bsError)
				elif state == 3:
					if literalRcptTo(Iterator(line)) is None:
						if testRcptTo(Iterator(line)) is None:
							recips.append(line[line.find("<")+1:line.find(">")])
							csocket.sendall(cmdOk)
						else:
							csocket.sendall(pError)
					elif line[:4] == "DATA":
						if testData(Iterator(line)) is None:
							csocket.sendall("354 Start mail input; end with <CRLF>.<CRLF>\n")
							state +=1;
						else:
							csocket.sendall(pError)
					else:
						csocket.sendall(bsError)
				elif state == 4:
					while "\n.\n" not in message and "\n.\x0d" not in message: # Weird ascii character is for telnet compat
						message += csocket.recv(4096)
					message = message.replace("\n.\n","\n").replace("\n.\x0d","\x0d") # Detects message end.
					domains = []
					for recipient in recips:
						domains.append(recipient[recipient.find("@")+1:])
					domains = set(domains)		# Set cast eliminates duplicates.
					domains = list(domains)
					for domain in domains:
						file = open("forward/"+ domain, 'a')
						file.write("From: <" + sender + ">\n")
						for recipient in recips:
							file.write("To: <" + recipient + ">\n")
						file.write(message)
						file.close()
					csocket.sendall(cmdOk)
					state = 0 # Reset state machine after valid transaction
					message = ""
					sender = ""
					recips = []
					
		except (KeyboardInterrupt): # Prevents an EOF error, allowing the program to exit cleanly.
			if connected:
				csocket.close()
			#print "\nGoodbye" # I can never be too careful with the autograder
			exit()
		except (socket.error):
			csocket.close()
			connected = False
			state = 0
			message = ""
			sender = ""
			recips = []
			print "Network Error -- connection closed"
			

main()
