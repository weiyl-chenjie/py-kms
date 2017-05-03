import binascii
import time
from kmsBase import kmsRequestStruct, kmsResponseStruct, kmsBase
from structure import Structure

from aes import AES

# v4 AES Key
key = bytearray([0x05, 0x3D, 0x83, 0x07, 0xF9, 0xE5, 0xF0, 0x88, 0xEB, 0x5E, 0xA6, 0x68, 0x6C, 0xF0, 0x37, 0xC7, 0xE4, 0xEF, 0xD2, 0xD6])

# Xor Buffer
def xorBuffer(source, offset, destination, size):
	for i in range(0, size):
		destination[i] ^= source[i + offset]

class kmsRequestV4(kmsBase):
	class RequestV4(Structure):
		commonHdr = ()
		structure = (
			('bodyLength1', '<I=len(request) + len(hash)'),
			('bodyLength2', '<I=len(request) + len(hash)'),
			('request',     ':', kmsRequestStruct),
			('hash',        '16s'),
			('padding',     ':=bytearray(4 + (((~bodyLength1 & 3) + 1) & 3))'),  # https://forums.mydigitallife.info/threads/71213-Source-C-KMS-Server-from-Microsoft-Toolkit?p=1277542&viewfull=1#post1277542
		)

	class ResponseV4(Structure):
		commonHdr = ()
		structure = (
			('bodyLength1', '<I=len(response) + len(hash)'),
			('unknown',     '!I=0x00000200'),
			('bodyLength2', '<I=len(response) + len(hash)'),
			('response',    ':', kmsResponseStruct),
			('hash',        '16s'),
			('padding',     ':=bytearray(4 + (((~bodyLength1 & 3) + 1) & 3))'),  # https://forums.mydigitallife.info/threads/71213-Source-C-KMS-Server-from-Microsoft-Toolkit?p=1277542&viewfull=1#post1277542
		)

	def executeRequestLogic(self):
		requestData = self.RequestV4(self.data)

		response = self.serverLogic(requestData['request'])
		hash = self.generateHash(bytearray(bytes(response)))

		responseData = self.generateResponse(response, hash)

		time.sleep(1) # request sent back too quick for Windows 2008 R2, slow it down.
		return responseData

	def generateHash(self, message):
		"""
		The KMS v4 hash is a variant of CMAC-AES-128. There are two key differences:
		* The 'AES' used is modified in particular ways:
		  * The basic algorithm is Rjindael with a conceptual 160bit key and 128bit blocks.
		    This isn't part of the AES standard, but it works the way you'd expect.
		    Accordingly, the algorithm uses 11 rounds and a 192 byte expanded key.
		* The trailing block is not XORed with a generated subkey, as defined in CMAC.
		  This is probably because the subkey generation algorithm is only defined for
		  situations where block and key size are the same.
		"""
		aes = AES()

		messageSize = len(message)
		lastBlock = bytearray(16) 
		hashBuffer = bytearray(16)

		# MessageSize / Blocksize
		j = messageSize >> 4

		# Remainding bytes
		k = messageSize & 0xf

		# Hash
		for i in range(0, j):
			xorBuffer(message, i << 4, hashBuffer, 16)
			hashBuffer = bytearray(aes.encrypt(hashBuffer, key, len(key)))

		# Bit Padding
		ii = 0
		for i in range(j << 4, k + (j << 4)):
			lastBlock[ii] = message[i]
			ii += 1
		lastBlock[k] = 0x80

		xorBuffer(lastBlock, 0, hashBuffer, 16)
		hashBuffer = bytearray(aes.encrypt(hashBuffer, key, len(key)))

		return bytes(hashBuffer)

	def generateResponse(self, responseBuffer, hash):
		bodyLength = len(responseBuffer) + len(hash)
		response = self.ResponseV4()
		response['response'] = responseBuffer
		response['hash'] = hash

		if self.config['debug']:
			print("KMS V4 Response:", response.dump())
			print("KMS V4 Response Bytes:", binascii.b2a_hex(bytes(response)))

		return response

	def generateRequest(self, requestBase):
		hash = self.generateHash(bytearray(bytes(requestBase)))

		bodyLength = len(requestBase) + len(hash)

		request = self.RequestV4()
		request['request'] = requestBase
		request['hash'] = hash

		if self.config['debug']:
			print("Request V4 Data:", request.dump())
			print("Request V4:", binascii.b2a_hex(bytes(request)))

		return request
