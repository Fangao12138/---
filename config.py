class Config:
    SECRET_KEY = 'dev'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///blockchain_copyright.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # local | fabric
    LEDGER_BACKEND = 'local'
    FABRIC_GATEWAY_URL = 'http://127.0.0.1:4000'
    FABRIC_CHANNEL = 'mychannel'
    FABRIC_CHAINCODE = 'copyright_cc'
