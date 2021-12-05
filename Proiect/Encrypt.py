from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

class Encryption_module:

    def __init__(self):
        self.private_key = rsa.generate_private_key(
                                public_exponent=65537,
                                key_size=2048,
                                backend=default_backend()
                            )
        self.public_key = self.private_key.public_key()
        self.chunk_size = 128

    def get_public_key(self):
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    @staticmethod
    def split_message(message, chunk_size = 2048):
        leng = len(message)
        reps = leng // chunk_size
        chunks = [message[i*chunk_size:(i+1)*chunk_size] for i in range(reps)]
        if reps*chunk_size < leng:
            chunks.append( message[reps*chunk_size:])
        return chunks

    def encrypt(self, public_key, message, is_bytes = False):
        if is_bytes == False:
            message = bytes(message, 'utf-8')
        chunks = self.split_message(message, 128)
        rez = b''
        for chunk in chunks:
            rez += public_key.encrypt(
                    chunk,
                    padding.OAEP(                        
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None))
        return rez
        
    def decrypt(self, encrypted_message):
        chunks = self.split_message(encrypted_message, 256)
        rez = b''
        for chunk in chunks:
            rez += self.private_key.decrypt(
                    chunk,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None)
                    )
        return rez
