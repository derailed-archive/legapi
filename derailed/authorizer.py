import base64

import itsdangerous


class AuthMedium:
    def form(self, identifier: str, password: str) -> str:
        signer = itsdangerous.TimestampSigner(password)
        encoded_id = base64.b64encode(identifier.encode())

        return signer.sign(encoded_id).decode()

    def get_value(self, token: str) -> str:
        fragmented = token.split('.')
        encoded_id = fragmented[0]

        return base64.b64decode(encoded_id.encode()).decode()

    def verify_signature(self, token: str, password: str) -> bool:
        signer = itsdangerous.TimestampSigner(password)

        try:
            signer.unsign(token)
            return True
        except itsdangerous.BadSignature:
            return False


auth = AuthMedium()
