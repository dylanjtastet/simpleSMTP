import sys
import socket

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

# Tests for errors in the <mailbox> grammar. Calls and handles errors for the
# <local-part> and <domain> sub grammars.
def mailboxtest(i):
	error = localtest(i)
	if error is not None:
		return error
	if i.next() != "@":
		return "ERROR -- \"@\" symbol must come after vailid local-part"
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
		return "ERROR -- local-part must be at least 1 char long"

# Tests for errors in the <domain> grammar.
def domaintest(i):
	count = 0
	if i.peek() == "@" or i.peek() is None or not isLetter(i.peek()):
		return "ERROR -- domain sections must not start with a number or special character"
	while i.peek() is not None and (isNumber(i.peek()) or isLetter(i.peek()) or i.peek() == "."):
		s = i.next()
		count += 1
		if s == ".":
			if not isLetter(i.peek()):
				return "ERROR -- domain sections must not start with a number or special char"
			if count <= 2:
				return "ERROR -- domain sections must be at least 2 characters long"
			count = 0
	if count < 2:
		return "ERROR -- domain sections must be at least 2 chars long"

# Unfortunately, due to the way a1 and a2 had to be written,
# this must be here for my old parser code to work. Since we are not parsing paths,
# it is more meaningful for errors detected here to spit out a mailbox error.
def pathtest(i):
	if i.next() != "<":
		return "ERROR -- invalid character at start of mailbox"
	error = mailboxtest(i)
	if error is not None:
		return error
	if i.next() != ">":
		return "ERROR -- invalid character at end of mailbox"

# Cleanly disconnects client from server by first sending SMTP QUIT command.
def disconnect(socket):
	socket.send("QUIT\n")
	socket.close()

# Main input loop
def main():
	try:    # Handles invalid arguments to program from cmd line
		hostname = sys.argv[1]
		port = int(sys.argv[2])
	except:
		print "FATAL -- Bad arguments"
		exit()
	# Initalize top-level variables.
	state = 0
	sender = ""
	recipients = []
	subject = ""
	message = []
	csocket = None
	
	# A state machine to control the order of user prompts. The FSM will self
	# loop if user input if poorly formatted, which will re-prompt the user.
	# The final state will format and send the user's data, and the program will abort
	# if an error is detected there.
	while True:
		try:
			if state == 0:
				print "From:"
				response = raw_input().strip()
				error = pathtest(Iterator("<"+response+">")) # Brackets added for parser backwards compat.
				if error is None:
					sender = response
					state += 1
				else:
					print error
			elif state == 1:
				print "To:"
				responses = raw_input().strip().split(",") # Tokenize and test multiple recipients.
				for i in range (0,len(responses)):
					responses[i] = responses[i].strip()
				for response in responses:
					error = pathtest(Iterator("<"+response+">"))
				if error is None:
					recipients = responses
					state += 1
				else:
					print error
			elif state == 2:
				print "Subject:"
				subject = raw_input().strip()
				state += 1
			elif state == 3:
				print "Message:"
				response = raw_input()
				if response == ".":
					state = 5
				else:
					message.append(response)
					state += 1
			elif state == 4:
				response = raw_input()
				if response == ".":
					state += 1
				else:
					message.append(response)
			elif state == 5:
				csocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				csocket.connect((hostname, port))
				if csocket.recv(4096)[:3] == "220":
					csocket.sendall("HELO " + socket.gethostname()+"\n")
				else:
					disconnect(csocket)
					print "SMTP error -- no server greeting"
					exit()
				response = csocket.recv(4096)
				if response[:3] == "250":
					csocket.sendall("MAIL FROM: <" + sender + ">\n")
				else:
					disconnect(csocket)
					print "SMTP error -- bad HELO cmd"
					#print response    			# For debugging server responses.
					exit()
				response = csocket.recv(4096)
				if response[:3] == "250":
					for recipient in recipients:
						csocket.sendall("RCPT TO: <" + recipient + ">\n")
						if csocket.recv(4096)[:3] != "250":
							disconnect(csocket)
							print "SMTP error -- bad RCPT TO cmd"
							exit()
				else:
					disconnect(csocket)
					print "SMTP error -- bad MAIL FROM cmd"
					#print response
					exit()
				
				csocket.sendall("DATA\n")
				
				response = csocket.recv(4096)
				if response[:3] == "354":
					csocket.sendall("From: " + sender + "\n")
					for recipient in recipients:
						csocket.sendall("To: " + recipient + "\n")
					csocket.sendall("Subject: " + subject + "\n")
					csocket.sendall("\n")
					for line in message:
						csocket.send(line + "\n")
					csocket.sendall(".\n")
				else:
					disconnect(csocket)
					print "SMTP error -- bad DATA cmd"
					#print response
				response = csocket.recv(4096)
				if response[:3] != "250":
					print "Server error -- message not recieved"

				disconnect(csocket)
				exit()

		# Allows user to exit cleanly
		except (KeyboardInterrupt):
			# print "\nGoodbye!"    Commented out to avoid the wrath of an autograder.
			if csocket is not None:
				disconnect(csocket)
			exit()
		
		# Catches any non-recoverable socket errors
		except (socket.error):
			print "Fatal network error -- aborting"
			if csocket is not None:
				csocket.close()
			exit()

main()



				
