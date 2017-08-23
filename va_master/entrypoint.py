import tornado.httpserver
import tornado.ioloop
import sys
import os
import ssl
from . import config, httpserver
from OpenSSL import crypto, SSL
from socket import gethostname
from pprint import pprint
from time import gmtime, mktime

def generate_keys(master_config, crt_path, key_path):
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 1024)

    # create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = "MG"
    cert.get_subject().ST = "World St."
    cert.get_subject().L = "World"
    cert.get_subject().O = "Master server"
    cert.get_subject().OU = "No organization"
    cert.get_subject().CN = gethostname()
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha1')

    with open(crt_path, 'w') as crtf:
        crtf.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    with open(key_path, 'w') as keyf:
        keyf.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

def bootstrap(master_config):
    """Starts the master with all its components, and provides the configuration
    data to all the components."""

    app = httpserver.get_app(master_config)

    if None in (master_config.https_crt, master_config.https_key):
        crt_path = os.path.join(master_config.data_path, 'https.crt')
        key_path = os.path.join(master_config.data_path, 'https.key')
        try:
            with open(crt_path):
                with open(key_path):
                    master_config.logger.info('Loading self-signed ' \
                            'certificates...')
        except:
            master_config.logger.info('Generating self-signed certificate...')
            generate_keys(master_config, crt_path, key_path)
    else:
        crt_path = master_config.https_crt
        key_path = master_config.key_crt

    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(crt_path, key_path)

    from . import consul
    consul.ConsulProcess(master_config).start()

    my_serv = tornado.httpserver.HTTPServer(app, ssl_options=ssl_ctx)
    my_serv.listen(master_config.https_port)
    tornado.ioloop.IOLoop.current().start()
#    tornado.ioloop.IOLoop.instance().start()
#    app.listen(my_config.server_port)