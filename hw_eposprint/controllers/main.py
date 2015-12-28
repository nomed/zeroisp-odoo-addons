# -*- coding: utf-8 -*-
import commands
import logging
import json
import os
import os.path
import io
import base64
import openerp
import time
import random
import math
import md5
import openerp.addons.hw_proxy.controllers.main as hw_proxy
import pickle
import re
import subprocess
import traceback
import httplib
import sys


from threading import Thread, Lock
from Queue import Queue, Empty

from openerp import http
from openerp.http import request
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)

# workaround https://bugs.launchpad.net/openobject-server/+bug/947231
# related to http://bugs.python.org/issue7980
from datetime import datetime
datetime.strptime('2012-01-01', '%Y-%m-%d')


SM_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
<s:Body>
%s
</s:Body>
</s:Envelope>
"""

import xmltodict
IP = '192.168.1.231'
class EpsonOBJ(object):
    def __init__(self, ip):
        self.ip = ip
    
    def _get(self, SoapMessage):        
        webservice = httplib.HTTP(self.ip)
        webservice.putrequest("POST", "/cgi-bin/fpmate.cgi?devid=local_printer")
        webservice.putheader("Host", self.ip)
        webservice.putheader("User-Agent", "Python post")
        webservice.putheader("Content-type", "text/xml; charset=utf-8")
        webservice.putheader("Content-length", "%d" % len(SoapMessage))
        webservice.putheader("SOAPAction", "\"\"")
        webservice.endheaders()
        webservice.send(SoapMessage)

        # get the response

        statuscode, statusmessage, header = webservice.getreply()
        #_logger.info( "Response: %s, %s" %( statuscode, statusmessage))
        #_logger.info( "headers: %s"%( header))
        ret  = xmltodict.parse(webservice.getfile().read())
        return ret['soapenv:Envelope']['soapenv:Body']['response']
    
    def status(self):
        msg="""
        <printerCommand>
        <queryPrinterStatus operator="1" />
        </printerCommand>
        """
        return self._get(SM_TEMPLATE%msg)
        
    def printXReport(self):
        msg="""
        <printerFiscalReport>        
        <printXReport operator="1" />
        </printerFiscalReport>        
        """
        return self._get(SM_TEMPLATE%msg)                

    def _printNormal(self, txt, op='1', font='1'):
        return """<printNormal operator="%s" font="%s" data="%s" />"""%(op, font, txt)

    def _printRecItem(self, line, op='1', font='1'):
        """
        {
            u'discount': 0,
            u'price': 4,
            u'price_display': 8,
            u'price_with_tax': 8,
            u'price_without_tax': 8,
            u'product_description': False,
            u'product_description_sale': False,
            u'product_name': u'Birra',
            u'quantity': 2,
            u'tax': 0,
            u'unit_name': u'Unit\xe0'
          }
                  
        """
        line['op'] = op
        line['dept'] = 1
        line['price'] = str(line['price']).replace('.',',')    
        line['quantity'] = str(line['quantity']).replace('.',',')    
        ret = """<printRecItem operator="%(op)s" description="%(product_name)s" quantity="%(quantity)s" unitPrice="%(price)s" department="%(dept)s" justification="2" />"""%(line)
        
        if line['discount'] > 0:
            ret += """<printRecMessage operator="1" messageType="4" message="Scontato del %(discount)s " />"""%(line)
        
        return ret
        
    def _printRecTotal(self, line, op='1', paymentType=0, index=0):
        line['op'] = op
        """<printRecTotal operator="1" 
                        description="Payment in cash" 
                        payment="6000,00" 
                        paymentType="0" 
                        index="0" 
                        justification="2" /> """
        """
        u'paymentlines': [{u'amount': 58, u'journal': u'Cash (EUR)'}],
        """
        line['amount'] = str(line['amount']).replace('.',',')
        return """<printRecTotal operator="$(op)s" description="%(journal)s" payment="%(amount)s" paymentType="0" index="0" justification="2" /> """%(line)
    
    def printerNonFiscal(self, txt):
        msg="""
        <printerNonFiscal>        
            <beginNonFiscal operator="1" />
            %s
            <endNonFiscal operator="1" />
        </printerNonFiscal>       
        """%(txt)
        return self._get(SM_TEMPLATE%msg)         

    def printerFiscalReceipt(self, txt):
        msg="""
        <printerFiscalReceipt>
            <beginFiscalReceipt operator="1" />
            %s
            <endFiscalReceipt operator="1" />
        </printerFiscalReceipt>
        """%(txt)
        _logger.info(SM_TEMPLATE%msg)
        return self._get(SM_TEMPLATE%msg)  

    def print_status(self,eprint):
        localips = ['0.0.0.0','127.0.0.1','127.0.1.1']
        hosting_ap = os.system('pgrep hostapd') == 0
        ssid = subprocess.check_output('iwconfig 2>&1 | grep \'ESSID:"\' | sed \'s/.*"\\(.*\\)"/\\1/\'', shell=True).rstrip()
        ips =  [ c.split(':')[1].split(' ')[0] for c in commands.getoutput("/sbin/ifconfig").split('\n') if 'inet addr' in c ]
        ips =  [ ip for ip in ips if ip not in localips ] 
        txt = self._printNormal('\n\n')
        txt += self._printNormal('PosBox Status\n')
        
        
        

        if hosting_ap:
            txt += self._printNormal('Wireless network:\nPosbox\n\n')
        elif ssid:
            txt += self._printNormal('Wireless network:\n' + ssid + '\n\n')

        if len(ips) == 0:
            txt += self._printNormal('ERROR: Could not connect to LAN\n\nPlease check that the PosBox is correc-\ntly connected with a network cable,\n that the LAN is setup with DHCP, and\nthat network addresses are available')
        elif len(ips) == 1:
            txt += self._printNormal('IP Address:\n'+ips[0]+'\n')
        else:
            txt += self._printNormal('IP Addresses:\n')
            for ip in ips:
                txt += self._printNormal.text(ip+'\n')

        if len(ips) >= 1:
            txt += self._printNormal('\nHomepage:\nhttp://'+ips[0]+':8069\n')
        
        txt += self._printNormal('\n\n')
        txt += self._printNormal('Fiscal Printer: %s'%(self.ip))
        self.printerNonFiscal(txt)        


    def print_receipt_body(self,receipt):
        _logger.info(receipt)

    def invoice(self,receipt):
        _logger.info(receipt)
        
    def receipt(self,receipt):
        """
        2015-12-28 14:30:02,607 18810 INFO ? openerp.addons.hw_eposprint.controllers.main: {u'cashier': u'Administrator',
         u'change': 50,
         u'client': None,
         u'company': {u'company_registry': False,
                      u'contact_address': u'MyPizza',
                      u'email': u'info@yourcompany.com',
                      u'logo': u'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASwAAACCCAYAAAD8HPVfAAAgAElEQVR4nOx9e3wcZb33pFdouZRbuaogIHI4iAge5HjDI9LsJtkkLUspF+VFreeI6PGuR885K4jQ7M79mcsz952ZveTZWzZJ06YthDtFelReRERARUQo9wItTZOZef/Ymc1km7RB06aed7+fz/OBJpudmd88z/f53R8Ma6KJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaa+HtFiz+aaKKJJg49eJ7X4nleQFQTw/Nqo0lgTTTRxKEAz/NaEonEPITQfJ+0gl+0xD1vfsLz5iUSiXlzeItNNNFEEzWyCv471QhrWF5T02qiiSbmCoFmNTIyssC27aNs2z4NQngmz/Pn8Dx/DoTwzFwu9x5d15chhBbFGzWwJppooomDgYB4RkZGFvA8f0w6nb7UsqxvqKp6O5RlHkLIa5p2h23b38709n5KKJeXI4QWYROaVhNNNNHEAUfdvEMILZJl+TQewi5V12+zLGtYUdVHRAifECF8QlGUbWnL2qIZRgrq+jWiKJ6dTCaXNgmriSaaOChIJBLzAsJBCB0t6/oneQjziqr+0bQsV1YUTxBFTxBFT5JlTzcMT1bV7RDCYSAI3QzDnIZhk6KKTTTRRBMHBiHCajFN89Omad6qquqjEMIdLABjDMuO0wzj0AzjMCw7zgIwJkK4U5Llp0QIoSAI3du2bVuIEJqPNc3DJppo4gCixXe0L2AYZrGmaV/TdX1E07TXeEEYTyaToykcH8MJwvHHWArHRzmeH4eS9BYvCI9ygvCflUplGcMwi4Pva5JWE000MduopyUMDAwsWb9+/UmSJFGCKP6F4/l3KJp2cIIYJ0jSISnKJSnKJUjSSeH4OM0wDgvAbpKiXqQoSiyXyx9ACB2NNQmriSaaOBAIUhgwrOa7KhaLZwsQmizH7aZoepwgSdcfHklRHklRHkGSbgrHHYqmXYqmxwiS3EHStJnL5S4sl8vHYdhkn1gTTTTRxKwgkUgE2eot6XT6uEwm82HA80WaZT2CJF2cIFyCJL1gkBTl4QThpXDcJSnKoxlmnCDJN2mGsfP5/EcRQicE39skrCaaaGJW0UhY+Xz+AkEUC0yIsHytqk5YBEl6wc/DhFUsFi9uElYTTTRxwLA/wiJIclrComh6EmHlcrkmYTXRRBMHDlMRFtckrCaaaOJQxHSERTcJq4kmmjjU0CSsJppo4u8GTcJqookm/m7QJKwmmmji7wZNwmqiiSYOBvbus/5XHBLRJKwmmmjigCGo0QuIZqrxboiiSVhNNDE78BemN89LePO8RGLakcAS8zzsf9fiCJPSNAt/xhqWT3LzvIlDI+qf+V9EWC2NzzlbpP53jHpTxqZcDgzqwvKwYMF681AczfemGSiO5icSNcLyScsff7eCr2tQ8Xh8fjwenx8+agshNB8htAghdLhpmkuHh4frwzTNpSMjI4dBCOt9qTBsMmF5nhcQVguGYfXrYD5hWZZ1AScIfw+Jo43dIFr8a87zZTTtCO5tiuPL/t4x5QY2E7nE4/H/zXKZPQREM4W25AvK/z2GTTuCz3oY5n+PNy+RmKRNHOpCr0+skMZT/zmGTZAOQuiIbDZ7IkLorL6+vn/o6+s7v6+v73yE0Pl9fX3/gBA6AyF0AoRwSUBEob/f6/sSicSCyy67bAHmE5aqqoc0YTVonnu942nPUZxCC51K88AO/bkyFSbJxJvi+LW/Ri5NrWsCIcLxCcmfiMG/R27QDxu5QV+2dU32xJ9fnXvPI9eU3v9gHJ219ZrM2VuvyZw9ErfOevh6dMbISvu0e+PohJE4OuLxOFo0sei92m6BHdK7xaR7C50DuEhV1SNLpdJpxWLxPMO2Py7LclQUxdUkTX8JJ8l/Z1n2R4DnfyIIwk8FQfgpJwg/BTz/EwDAD2mavhkAcKMkSVcZhtGWy+U+WS6XL0AInVXNZk/Udf2w4EzBQItLJBLzIITHH6KENUlG9blSW5yB5nn44ODgMWj9+pMQQu+tVCpnVqvVs4rF4tnFYvHsSqVyZqVSOT1XrZ5SLpePGxgYWAIhXNhoDv2daRd7zZ3GMTw8vDSbzR5frVZPKZVK70MI1WVSLBbPLpVK7/d/flImkzlmaGhocaCF7kMu//8gICTkL5LpPjewNnv8XTda5zwcR5f+PI5aH1rTe9WDV+euuW915vP3rc58/sE12TUPrOlddf8a9Ln7ry5efH8cvff+G6tHTnfNBs3lkMB0i1pV1SNzudzphULhinw+f7NhmkBR1SFeEH5DUNSfelKpl1M4/gZOEG8RJLmTIMmdeG28TZDk6wRJbmcBeBbK8mOmaW7K5/OwVKl8r1IsrikjdGm6XD4uMTKyIHTJFs/z5mmadoIkSR8GPF88VAhrBr48DMMwbHh4eHn/xo3n5fr6PolKpbZCoXB1uVy+tlIqXV9C6PpCoXA16uvrRgj9C0Low7lc7hTTNJdO8VVTabqHHPYnF38DWlgqlU6rFosXVkulz5QLhc5CoXBtpVK5rlSpXN9bqVzXWyxeVSwWO/xN7dxKpbJs27ZtC6e4ZEsDef3vRqBFYcGOgGEt8KK1CwcuSiy55+rce7Zegy56YHW+8554Zu2WK/X/GFwJU+UuoKI2qlTu4IY2rJQ3D6/U7ty8yrhr8yrjro2r1C3ru6VNxQ52IB8l85UOwK/vkm7d0K1/6+7VmfjDa8qXbrg6d/rQtfZR/i34153Q6OZGELUDSBsPHx0eHl5erVYvzNn2at00fyDpuqDqekU3jPsVTfs1lOU/cTz/OsOyb1E0/Q5JUaMESY6RFFUfBEWNkTQ9SjPMO4Dj3uJF8TVJlp/TDOM3lm1vVWR5i8hxCApCSlXVm3ozmWjeNM9FCB0NIVwIADgOQng+4Li51rBaptJ2tm3btlBV1SNRf/8Zpf7+j6FS6cpsPv9V0zR/rKoqKUpSmuX5igjhBt0wtpiWdadp23eZtn2XkU5vUXR9mBOEPpplM6IkMaqqJtK2fXOhUOisDA5ehBA61SexvTS6Q2SRTmnG6bp+WDqdPq5YLH6wUChcZmez12ma9k1RFH/CAABols3wPF+VZXmjaZp3mqZ5l2nbd6VN8y7NMDbLsryB5bgSSdMGL4pJXde/b9v2l3t7e1f09/efN5DNHq/r+mHYoSuXWUWdJBKJxDy4Fi7c1jGwZLjbXL5plX72+ii4ZGOXdNWmK/Xv33WlqW6JpzdvXKk+Ue0U/lzoYN7IRPGxfBvp9XXybn+n6A52Se5gl+T2d4puOQbcbBvuZFqTu0vt9MvVTuHpoZXKI5tXpTMjV2X+e3CVfN3glfInh+PmGUNx7YSBtXAJiqP5wb14B1+9rZ+YnEgkFiCEDkeadoJhGGdmenuj2Wz2u5Zp5lRN+x9BUV6BsvwOlCQXSpLL8bzHsKzHsKxHM4xH0XS9A2h4+CTiMSzrsQB4gOM8EUJX1TSXA8BjKGq3wPN/VmX5bss0ecuy1uq6/kld108XBOF0hmEuCBMWThDeQSasSeaNH2A4Qtf1k0zTPNc0zU/Y2ex1dj7/X5ls1rZs+x4jnX4SyvILgOPeomh6nAXAg5LkyoriKprmKprmSoriCqLoUjQ9RlLUTl4QtsuK8ls9nX7AzmbVbG/v9wzDWKVp2iUmQu9FCB2r6/phyD8k9hA43XoSgQ8NDS2uVCrL0gidqqrqBZqmrchkMmszudwdhmlWFFV9WBSEZ2iGeYmkqJ00w4xzPO8pquqGB5QkF3CcR1LUHoIk3+QF4c+Kqv7KMIxNtm0zuVzuJkvXW1VVvSCXy52CEDrafyeHilxmD56vRmKhBxrpqix7qDt/7paV9uqN3cpPBrtEVI5xD5Vi4Jlqt/iX/i7htb5Ofmcxxu7Ot1NjmSju2pGUa0WSjh1JjWcjybFsJDVmR1LjViTp2K1JNxNNOaiD2lPuBLv6uoQ3+7vEF/u7xWf6OoVfDHbLpU1X6rdtXmOsGr5B/+C2tXBJ/f4O4g7hTRztjmEYhiGEDq8idFZvNrvKtu2UruvDsqI8LcnydhHCNwHH7aEZZoykqHGSosYJknRC7YoDzWev0fgZ/3MORdPjJEk6JEk6HMfthpL0uqppf1ZU9ReapiEoy18XBKGd5/mPsRxXoQHwCJ+cDiJh7TVfstns8blc7sK0bX9B1/UeWZYHZFl+RJbl38uK8qKsKK9LsryTF4RRFoBxiqZdkqJciqbHSYoaC2mhgQwdkqIcFoBRQRR3SrL8hqwof5EV5UkRwgdlTbPMbPaHaduOyLJ8hq9Z1N/hHGgULRiG7RUQGBoaOq1cLn/atu2bdV0XZEkaURTlUUXTnpVk+WUoSTsEUdzFArAn1Ora2ZdcKJoe53h+twjhW5IsvyYrynOyovxakuXNiqpyuVzuX23b/nh54vDcuZTL7CLQYlA8Pv/xOFq0caV18vpV6sVDnfLqwS74nwNdcqa/W3ywr5P7M2qn3s63kW5vO+2idtrtbaPcXBvpZtsI14okPbM16aYj6xwz0jNuRtaN1/7bM56O9DhWa9K1IkkvFyXcfBtV/45CBzNe6GBGK53880Mr5Z/3d0OrfyX8j41Xyp0j3eY/br4cHT0UYRbXHPMHdIeoq84IofkQwoWZTOb9uq5/TtO07+i6buqG8UtRFF/heN4FHOeyALg0w7gESTo4QTgpHHf8VsV7kVXjz6YirNBpNw5JUS7Dsi7gOJfjeZcXhF0ihH8SBGEjx3ECSdM/Imn65yRN70VSB5qwgpN7BgYGlpgIvVezrH9WNO0Lqqrepup6UVaUbaIobuc4bhcAwAUcVx8MywYy80LPPJ7C8XGcIIIRkL5HM4zLTv6OMcBxb0NJ+r1uGPcoqiopivJNy7JaLcs6J3DSz4FW0YJhWAuEcGGlUlmWz+c/YNv2Z03TvCmdTjO6YWyQZfk3PM/v4Hl+lON5FzTMI5KiXJwgwvMgLJfwRugxLNsolz2CKL4qyfKvdV0f1DQtqarqFy1d/2RGUd63du3ahY2pNwdJLrOHmlO9ZnqNXJZYsPlydPSmbu3TG1dpP+nvEu/s6+S3l7vAaLGT9VCM9TIR3E2vWOcYK9aNGyvWjadX9IynW3scM9LjmK1J14qkXDua8qYaViTlpluTrrmix0mv6HGMFT3j6RXrxtOt65xslHALHYzX3yV6lRg3Vu7gXti4UqluWaV/Y6A9cza6HB2NYQc2ZyiIZmH+pFNV9UjDMK7SdV2RVfUZKMu7oSx7DAAuThDuFBNpStMvdCDEJDLZz+fqBJbCcSeZSo2TFOWyAHgcz3ssAG/gBPGU79B3cYKY9P0HkrCCzyKEFq1fv/6ktG2365ZFSYqyVYRwhyTLYyKEHuA4jyBJJ5lKhYloPFiMITKfTg5TL14cd2iGcTmO8yRZ9iRJekeW5d8bhpG1bfvGXC53ysDAwBLMD1AcBIf8pMU/MDCwBG3YcE4ul7shY1k5WVWfECVptyTLjiCKnm/CO8kQQadw3EnhuJvCcXcmcknh+KS5kUylxlM47rAAuLwgeFCSPChJr8my/AsrncZN0+z43ve+d+TatWsXHkS5zComHHKY17Ipxp4y2Ml/shoTvt3fKZgDXdK2Ugw8jzqoXfk2YizbRjjZCOHarSnXak1OHpGka0dq2pMVSXq2P6b6t1n7/73+3ook3UwUd/PtpJNrIx3UTu/s7+L/2N8l3N0XE6XBmPKFzZ36+SNx7ojwfc+WMIJdB0K4kOf5YyCEn1AU5XuyqhYkWX6C4/k3GQDGaYZxptGW9ktGjYQykxFcK9DaSIpyaYZxqZrDfgdBkqNTkdVsE1aj41aW5TMkSYpAWU5IilKUFeUxQRC2swCMsr6cKJqedO9TjGnvu0FT3FtDJUmXomnXPyx2jOP5N2VZfkpW1Y2KouCyLK/UNO39EMIlgZ8Nm32NYq9UFyObPU83zWtkTaNlVd2saNrTvCi+zgIwzrCsE2hRBEm6+LuQSaNcfH9lWDN3iQmZuMGxboIovixL0v9VVbVXUZQfyrJ8GaNpJyCEFh1Aucw66smPAx1wyZaYfOJQlxQZ7OR/0tfJPVDuAC+VOzg33055mSju1rSnHsdqTdbNusnaU7I2IpNHI2HZkeTEZ6PJ+t9a0aRnRnrcdOs6Nx1Z51itSTcbxb1iB+OWYuCdUgd4tdopFoZXKl/d2K1eMNKlL2vImP+bECTfMQyzmKKoEyGEn5AU5ceSLP9cgPAlXhBcqmZ2uSkcn1Kbmo6wwj/HCaI+3gVhTZqkvsbh+uZi/XdTEeIsEladrDiOOyKdTp+qKEpclmVagPBRQRTfEEXRZVnWo2jaDWlQk2T1bp95X6Tva7j190HRtMcLgitC+JYI4Z9kWZYVRblGVdVzbNs+6kAszHqOWSIxj9T1ZdAwztRN88uqpmUFUXxWEMXdIoTBe6prRGGNeKYa+bv4bP06JE27DMt6giC4EoQvq6r6C0XTbhUN47OyLJ+GEDo8nB83m7KZTdTICqu9wJGYddZdnfo1G7ole7BLfLocA6/3tlGjViQgpx7Xak0GznTP8gnGmkRIqcmj0Rys/24ykYX/NvheO5KqXas16drRpJONEuP5NmZPtUt4aXiV8tCWbuMn93abn/bCO9vfIOyw1kCS5Mkcx12hKIokyfIvoSS9yQKwm6j5pyZpUzMx8cIEE/ZNNY79EeA015vRjjwLhDXp54ZhnGfa9k2GYVQUVX2OF8W3GAD2BOTUKKe/hpRmsmgb5eA/4zjDsns4nt8NZfk51TC2WJb1jVwudzE2Of3ib0VdM/ESiXkjun4YVNVPiJr2M0lV74KS9CLguHd8eYdNX3e653g3Mpkh+Ye1Nodh2VEoSW9JivK4rKpZTZav1DTt/cGzhCstDiXUM9aHrzeX3rXGOO/OK9Nf2rJKRwNdwlOlGDueb6ecTAR3zdYex2ztcc1IzwS5RFN7kVXjCAinRnAp14z0eKZvClr7IKww0fm/c81Ij2NFkm42QriFDsatdvGvb1qp3z/Sbf50U8z4+MYV8OSGsp93Lw/Pa2EYZjFE6GhJVWOyLJOyojzmR/8ckqICYmk8oHSfE8XfQYMomEvVzLi9BknTLlHbfYO/3e/u2nCtA0lYdU3ctu2jNMv6iGmaX7dse0hWlGd5QfBYAFxyQqua5EubycIiGyKnM9E+p1m8rh+ocGiGcVmOc0RJetk0zQ3ZbPYHlmV9RNO0E2ZJm6i7D2RZPlGSpMslRbkVquojvChuBxwXdqA74fc0U/L5a+QyxXsPNkyHomkHcFwQuHlGUhRTVdUvGoZxJkLo6NAcOGRIq6Vev4dhLZuuzp2y5Wrjpi1xY2hzXHdLncCzo6kgwudMMvsCLWgKbcqKpDzL92ulW9e56dZ1rhnpcdKtNcd67Wc9NWf7dBpZJDWZxALiivrEVXPqj+faCWd4pereucr49aaYCjZ2yp8MVHIv8e66QITsdwwidDSvqueous6pmva8JMu7Acc5yVRqzJ9wM93dXN8J6gSHlzIs67Ec53E87/GCUB+A4zyW4zw/JcFN4bibTKXqxPhutZPZJqywz2pkZGSBZVlnGab5Y9Oy7rUzGY8XhLrjl5hCQ5xOewiTeuBkDmub/r8naY/7e8YGs9lNplJOiiBcBgA3nU67mUzmEcuy/tOyrI9M97zvZt4Ef8tx3BGCIPwTz/OKCOFvZVX1WADGUzg+NpVcZkK6f41cZrLBBUEimmFcThAcSVVHFcPYkLbt1YZhnIkdao74BOaXBmBYS1+nfv5Qt/7lzVcag+tXSs8WY6zjpyXUzb9A02nUgAJSMSM9nlkjIaf2NzWiqaUskG6+jXRzUdLNthFepg0PooSBtuWYkZA/rH6dkAYWTU4yE83WHteKJh3UzjiVdv7VwQ7460or/7Pez3KfGWzjj/EwrwWboZ8iVNM2f0TXD1MU5VOCLKdkRXlYkuW3AcftCTQrf4ebkgjCRBUkbbIAuCwALkXTHkXTu0mK2kFR1Haapp+jGeb3FE0/Q9H0Hyia/jNF0y+TFPU2xTB7aIbxQC207YW0LXcf13w3O+1fTVgYhmE4jn+MAeC7oiTdJUL4F57nHYqmncYFtB/Sqkc9CT8jn6Qoj2YYl2FZNwjR+3IL/ra2SBv8YdPJpEHbckmKcjmedyRZ3m6k048YhvFD27Y/atv2UdhEcudMUU8FSIyMLCAQOlwUxQ5JkigoSb/iRfF1mmUdkqImpR5MORp8cQ1R073kwrCsG04+Dp6vUXubyTwgajlcDsfz46IoPqsoygZJVb+sWNZZQYBizvO0gqRQFCcO3xhXjh3s1m8c6FKLG1bK28sxzjUjyfF0zbHu1kkqRE6T/EyRpFeP7EWTTiZKjNvRlJOJpNxslBjPt5OjqIPe1dtO+YN+J9dG7slEcceO4K4dwd1MlBi3oqngevUI414O+4CwoinPjPR4NU2tx8lGCKfSxrmVKP9ApVW8dX1U+nA1ph5ZI6z9Crvuf4AQLsno+tmyLH8byvKTgii+wfG8S1JUkKqwX7LwCc2hag7OcQjhW1CStvOC8EeGZX9FkuQ9BEEMkjiOCIIwcZJMp3DcxgmiSFDUBoKiHmABeFwQxedkWX6VF4Rd/qINR8YONmEFJs8SCOHJLMd9kwHgTsDzrzEs6+AEMY5P5JvtT5vyiAkfjkNQlENSlEvVop3jDMuOsiy7C3DcThaAXQzL7qYZZg9F0/VorJ9AuRcR7EtrCZtDLACOoqqequvDhmF8U9f1DyKEDn83mlaoiLsFAHAcJcsfEiUJlyTpN1CS3mY5rpamMAMCIUjSwydIvJ4gGwyGZfcwLLubBWBXMBiGGaUZZsyXS0DgwZiRRh4mSJqmXQCAI0nSqCRJtqxpq2VZPi2RSCya08hhQFYehrVs7oDv3dApRjd0y9mBLri90M7szkRxJ926zp3QdkImWsjBXtOoetx0a81kzEVxF3XQXl+X4ObbKNduTY5Zrcm37GjqxUwUfyYTwZ+0I6nfWRH8WbM1+ZK5Yt1OuzU1lmsjvUqMd0sdwLWjuGdFkk46ss7xtbWGvK0GwowkvXRrj2tGkk4mijt9nfzrG7rVh7d0G1/f1KV/GAsVw+5DJHXCSqfTp2qa9jVV0wYkRdnJclzdeTyTSZfCcZeiadc381wRwjc1w/iFaZr5dCZzi6rrX5YkqZ3n+U8DAC6hafoiEoCP0Dx/EUmSl4oAfFZRlC7DNL9u2DZpWdaQqmlPCaIY5FqFQ9YHi7DChP5BHsIv6YYxqGjaawzLjhIk6RAE4ZD7MHf8awZmiIMThMOwrAt43oOy7DIs6xAkOUqQ5JsUQbxAkuTvSIr6LUFRv0sRxHMESb5C0vQuiqbHGAA8KMsuL4quT0SOHxmc0vSZyhQia/lrLpSkl1RV3aIaxrVGPn8mhs0483tSkTUA4FKO45KSJG2FkvQ2w7KT5s3+3Aa4n2RMkKQLanlTriCKLs0wYzhJ7iJI8lWCJJ9LEcTvcIJ4EifJpwmCeIEgiDdwghhlWHac43lPhNAFHBdoWzMOwgTETzOMw/G8y4vi76Ek5RRF+Ww2mz3+Xchl1tESJISiOHfE+pj4uaEY5Ps7xV+XY8DNRPFawmekx51s/oU0nLBGFUm62Sju9raRY4V2emelk/vL0Erl0XIHGMm3EqVMFFesSA9ltaVusyLJW6wVyVusCH6H2ZpirBUprTdKVcox7u71K6VHq53Cn3vb6N29beRYro1wag76ZM3J76c9BNcPm6UBcZqR5Hihg3H7u8SXhzql6oZO5Sv3xrUTHoyjw/fu0zUhD8zXHhBCJ6TT6ct1Xc9Jsvx7rla75oQ1q31NOnIiC32XKEnbJVl+WFGUTDqd/o9MPn91b6n08XK5/IFyubx8aGjoqIGBgSW6rh82NDS0WNf1w8xkcmmlUlm2fv36k1Bf3/lZhD6Xy+VuTFtWj6qqG6As/5YXxR0My44F+UwHkrDqUS8/CJHNZk/UNG21pCgVRVV/DyXJDZvJ+yKrkCbk0jXNc4zjuLdECP+k6vr/CKK4iWaYXpKmZYqiCCKVupUgiJ+kCOLWFEH0EBTFUSyb5ni+X5Sk+1VdfxzK8osMy46xoVy46Rz80/mGOJ4fFyXpz1BRVElVV+m6ftjIyMiC/SzO+pyBEC7hOO4sThC+xvH8No7nXwIc5xATBDSjeUPRdCCXIDP9KUVRHuJ4fpBmGJOgKA7H8WQSx29J4vgtOEn+lCAIgiRJSDFMlhfFjbKqPqxo2lNQkl5lAahXD5D7iB5PpfXSDONyPL9LhPBxAcKELMufDDdOnGINHTDUUxeGIszi4U7uPQMx+N3BTvHVYgf7ju+zqvmRosm9nN92KBpottaidXZbyivGgFftgqN9Me7F/i5496ZuHR9Zad7wcHf20pEu/fQt3enjhq5ljqrG1COrMfXIbWvh0Q9cby6/85rS+x64pvSpe662b9wU1/HBbril3M69Vo0Ju/s6OS8Txb106zovvWLdJNKypyAtuxZ9dOxIys23UeN9MX7n+i4pu2mVevHImuzxGIa1eFitwWBYIGFNwjTNi03T/IGq688IELo4SY7jEyHofe6SQdRFkmVX1rTtUFG2qrr+H7lc7hII4dF/w0tuKZVK7yuVSm1aOq0pqvoMlKRd/i46Pt1EnC3CCkjLHho6KovQpYZhkKqqjvE8P0bR9HgoZWHf5o5PajTDeKIoerIs7xZF8U+yLG+w0ulbcrncaoTQRbm+vveAdPo4hmGOUlX1SNu2j6qTOEJnFQqFK3p7e28ybVtQNe0BEcKdUJLGRAg90g9UTJXTNAVpuclUyqEZxgU8PyqI4l9EUSQZhjmBIIjDw+belOvIl4sgCMtZll0NeD7HCYLnb3DBe9mfdhOO1nl+NvrbUJYf0zQtY9v2t3t7e6Plcvlcq1Q6uVKpLGrxLswAACAASURBVFNV9chALgihY3N9fe+xEToflUrd+WLxB1YmYxvp9KOKqnqSLHu8IHjBpkKQewdCpnhPbgrHx1kAXBHCHTyEWwUIvx0Qecg0PCikVe+8UFpJnpy/sudL5W663N/J7+5tJ8fM6ITTO5yqUPNfhTSr1pSbixJubzs1XozRo/1d4q+GViqZ/k7x+9UYjG/pTl96X3f6A1tj2RMfj6MjnooMLd62Fi6Ea+HCbRfBhY/HE4v+cMPIYSNxdMS915VOvv8665zNq/WPrV8lrarGxG8NdcvG+i75kXIMvNFbS6nwneyhzPmpUykC03C81MGOVWL8tlI7/7NSB/8xFEfzERafH44ahjPZEwMDS0RZ/iKU5X4Rwlc4np+xA5MgSRdwnAslaYeRTj9imCYQJOkqWZYvMk1zOcPUah7D/Yj2N/yJMQ+rBQKOQAi9V9f1z8mq+l1ZUTaIED7L8bxLv0tNa4aEFTajWyCEC0VRPFuUpB+LknQvlCSHrZlwMzF5XIIkA81zD8fzb8uK8rBmGJqoqt+CitJlmubF+Xz+zIGBgePN4eGlzNDQYgjhwmAghBY9+OCDhw8NDR1VKpVOy2az52Wz2U9ohrFGluUfaYbRq2naYyKEbwMAPKq2GKfUthpNQ6JmBo2JEO4URXETSZJfIknyXH9BBu9g8hrytYyhoaGjNNO8RICQ5wXhMVDzdbphjXN/mhULgAt4fhfH8y+LEG6RNI2QZfmLsq5/LpvNfshvZrgMQrgEIbQokMm2bdsWDg0NLR4eHl6KEDq2UqmcjhD6sJnN/otqGF9UFCUpSdKwIAh/5Hj+HYZl3dD72C9pUTTtsADs5nh+Oy+KFsdxnxEE4VQM27vA/YAhICvziuRSe+XtH82sWmeilcQz5RhwM224Y0TWOWaj6RfkWvk+K6s15WaixDhqp0bLMfbFgS7hV8MrZWYknl59Z5dx5kAHXIK9ewau9UtaO7Dk3uusk++Mp7s3r9J71ndL9/fFuOcL7fRoJkqMW621PK59EFbdn4XaabfQzr7U2w5+3tsGvlDu/tlx6LzEIi+kzgeDYZijkix7BuB5EvD8s8ELnglhBY5jEcI30un0r7LZbCqfz0duvvnmxUFf9nC7lZmQVqN2EwyGYRbrun62qqrfkhWlH8ryKywAu8iGBMTZIKz4RIPGFpjNHg9V9QpeFAc5nt8OOM5rNEn3RVgUTY9xPL9ThPBZSZYf0NPp2y2EYkom8z4CocP/2vlSrVaPRAidYdv2daZl8bphbIOS9DKodX0IklanNQ8DzY8gSUcQRVcUxd8zLFviOK5jYGBgSSKRWID5m0Zw3fBiRQidZZrmDZIsP8wJwlvhQuV9yYScML328IKwQ4TwCUEU10ua9h0rl/tnCOHx/rXfjVzqn4UQHq8oyoUQwn+XRLFXkuXf8ILwBj1RED8laTXcb9D9weUFYRsnCAlBEP4pkUgsiO+neeesIJGYMIfk1beea8VvW5u9MvmLbGdqlx1JOVbrhK+oTlYh88vPqXJyUcJFHfRoKca9UO0UykPdyo3Dq7RLHug2l6M4OjxxWWIBiqP5XrAwG2qrsFBSp4d5LQks4Z+q480buWxkweNxtGhkTfb4LavSHxpcpXyhv1PS+zqEF4od7M58O+VarSFNKzo1sdaijCk3GyVG81H6TdTO4NWV7Mc3x+HR/rXnoVDTfpIkT0+RZBcAYAAA8E6once+bP56nRYLgCcIwgOqLN+m6/rHEELHTkE6GPZXLEoMq2mCwWEDEMIlgiCcDhXlC6IkDQgQ/tGPYs5I0/orCAszc7lLNMP4EYTwNyzLjvptbvarQQSOdV4QdkJJelJSFFVV1W5VVS/I+k3lZnCwxKS6vKAY3fO8eRDChbquH5bNZk80TfNiLZ3+mqyqZShJOwHHjVE07YWcz9PJIniPDuC4tyVZ/otpmj8YGBg4e2BgIAjph3039fdp23a7YRiCpCjPAo4bI0iyPm/25cvzo5QuLwg7RFF8GELYoxjGpxTLOgv6zRj9XmKNfqN9yiXouuBrpUcAAN4ny/K/aKZ5q6wo94oQeiwA4efel6blkrU2Pi7H89t5CLcKknStbdtHBV0vDqSm1ZLAEvOQf0pNvjvZmevGpd5u8vlsR63TwqR6wHpC6ARZ1QgAd1E79XYpBp7q6xTs/i64dtMq/extcXT0xEETodavE9nm05CWN/nz/ovxMK9lWwdcMrBKP7u/S15TjUFYiXG/KHTQb2ejxFhQprNXRv3knDAnEyHc3nbGK3YwQ32d9E0DHfC9KI7mJ/z+RMHgOO6jgOdvFQThfwAAHjFRdrPvSV7Lnn5DEMWnBUFYByH8DM/zx4Qn0myWfYTb3HCyfK4oy/9HhLAkiOJfWJbdPRNH/Ls0CRcghBYpinK9rKoFURS3syw7qXZyOrIKnLeA518XJOlRKMtAUtWrLMs62TTNpfV37U1+//sjrMbPBz9HCB0hy/KHFEX5iqKqRRHCJwHPj+4rB6ohR8thARiXFWVcT6cz+Xw+bprm8oCwwtouwzCLEUJHa5r2HUVVHxRE8Q2GZd1kKrU/E7kWmGEYhxeEF0RJuhdC+N+SJF3ua4uLws8/lZY9nVymkmE8Hp8PADjOyGQ+ZRjGjxRFuVcQhOdZAOq5YVNpoA0bsgM47h0oy68KEN4GAPiIqqpH7sfH97dNdiwUGdQvSxxW7OB+UG7nflnuAG/m20gnvWLdeK1Ob3LaQNBJId3a42SjhFuKsV45Bp4vx0B1fUxpHe42l2MYhnmJxLyRyxILPOzdZZZPda+JRGJe/RgwzGtBceXYbIz/UF+ME8ox5vlCO707FyVcv/B6CtLyTcNIcM/Aq8TYp0odlF6Jch9GcbQIC71khNB8SZLaoSQNQ0l6juP5wEk57YIMku1ALYz8tCCKvaIofi5MggeysBbDahrz2rVrFwqC8DURwnsghK/7jvh9kslMne6YvzBJklwmiuKtgij+jheEnQzLOikcHyf24WjHCcKhGcblBcETIXxSlGVNFMVLGYY5Krj3Bu3hr0X9HQZaUDqdPlUxjM8qmpaXZPkNwHFjNMPsTy5uqtaexoGS5OmG8ahZSyk5Kyz3QPYIoaOLxeLZsqoqIoRv0Ayzx/+OvTq81mUSyIVlXRFCD8ryg5Ki/ARI0gd88w/z/KO8ZiES19JIdKZpnmsYxlq1Vte4h2HZcYIknX3dcyAXhmUdRVU9QRT7CIr6IkmSJwcb5wEhrCCcP3gNf0xxFTgv105JuSj5Uq6NGM3UMsadcCZ7QFg1n1VNu+ptI0f7YtyOvk7Ornbx1w2u0t4/0AGXBKZmoGHN1v16WK20ZuQG/TAUV44d6BS6Bzp5UImB3xfaqdGJ2sQpCCtaNwu9XBvp5aP4G/k2/N6hTvHKrdeWTsMmfBCLBEFYznDcV2iG+R3guDd8lXmfk5ukKJdimDFBEN6EEFZlUbxS4/n3H0iymiSfkKYBIbwEQvgDCOGvOJ5/e6Zh7BkQFlYul5cXi8VLRAgtwHGv0wyzZz8+mgnNiuPe4UXxFShJoijLnYIgnIrQxKlIsxgenyQPjuOOENLpUxVN+4KsKBaUpD8Djttv1C7IzfJN2JcUVR0yDOOKcrl8HIb5JOsXA1sInWXncteomrZRhHA0iJZOFZkMy8U3r14XIXxSgDABIbyEJMll02iYsycXz5unIHSsaZrniqL4fQDAFoqmXw00y33JJcgrFETR5QXhcV4QeFoQ/jGRSCyaxXudQHhX7o+zZ1RXiytzHdSGTJQYr6cwhMzBSRqW35khFyXcQjv9SjXG/6raJfzbyLXyaSM36IcFZuaBOrU5qAfEMKxlZKV92vAqpau/k99Q6mBfzLdRbiaCT2Mahv7dmnQzNcJ9ekOX9MO7V9sfDb7fNM2lhmGcBwD4CUGSb1I0vcfvejnd5HaDXRJw3E5BEH4LBeGnZjK5HBHE4dgUrXAPiFxCpqau68tEUfwUhDDPC8IfAcfVc6PeNWEVi5MICyF0TrFYvFGS5RE/YXWS5jmNGeEwLOtxPP8CD+F9oix/XvN7LYW0oQMhn0mBAj2TOVs1jM/LinIPL4qvzoDI6wm5LABjEMLHDcP4t3w+fy6GYZjv81zgYVhLOp2+NJ3J4IqqPipCOEneUySpeoFpJYjiOJSkJ0RRTPM8f3kikVhQL+05QPPG87yWuOfNT9SaUGIkSV5KUdSPSYp6jKSoXeRE9cC08yQgco7ndwgQ3g1V9QpFUY4N5D6r9x3e8Yfj8kWb4tp/9XVxjxQ6GNeKpBwzknTs6OTFXm+s53cLzbcRXiFG/bLSxf6supL9+MgN+mEjlyUWHIzFGZDiyA36YdUYf06hjf9+qYO/sxQDbjZCuOkVEwXUU/iz3HTrOqc3Srl9HdwLG7oU/c6V6e7gngcHB48p5PNXqKoKfSft/mq+XJwgHMBxrgjhiwAAk6bpq1CtdOGgyCOEQMNayMryGTQA3wIct8nv0xVkk78rwrLz+Y+GCSuXy/2zZVmsoiiP8YLgTmUqh0krMJVphvFYAB5kOe4bjCBc6JPVwZBP3URMmuZSFsLzGQBuAxy3lYfQo2uh/X363vz360BZ/pOmaZRhGFdgGIb5ZLgAw7D5iqJ0qKp6lyRJzwdyIcjpTycia6U1YyKEb8uyXFJV9QpN097TYGoeOLmENFCSJJeRJPlxgiRNmmWf5gXBC23Sk+6/wcfnMiw7JkD4m3Q2ezPq6zsfwyZ35J2de8X8/jyXJRZsXCVdPtgt2X2d3FPFDnZawgrIyo7gbjZKjKEO+o1CjEHFTnZFrpN7z8E8JzBo15xIJOZl2m4/BkX4Txc6AFnuBK/l26jddivuWkE2fCNhtSbd9Ip1471ttFuJ8a9XO8W7Bjulrz51M7PYS3jzqtnsicXe3uvS6XRBkmWXZphak7NpUgSC9AGO5/cIEP6GYZh/x++444KDNvEmo+705Hn+GJJl/4XlONYPr++ZTpuYjrAoms7kfcIKujGoqhrTNW2TJMvT+vYavs+lGWaUBWA7A4BK0/RFDMOccCAdtI0IfCuJRGJeKpU6nsLxGMtxiihJbzEATCuXxg0JStLLkqJUJVW9YWRkZAFCaD7DMIsBAMcJgvAVQRD+wAvCmyzH1TXyKQgr8I25vCC8KYjirwRBSGSz2RP9tImDOWfq74AgiFNxkvw3mmEGOZ4fn26jDhNW0GoZStJzacui8oXCFRiGYQk/YovNxrsNfEpeIjFv4CK4pNIBrip1cg+UYuyLqJ32aiZhjzsFYblGa4+Ta6PcQgezq9DO/K7Uwd4yctnIEeg8tKje5eEg1RV5ntfiJbB529auXVj9+LojyzHwhXIn+5tiB/16bxvpWdGkY0Uan2OCsPJtlFuKcTuLMfDbSoy95Zc36Msej6NFpVLptEqx+I1MJrNJ03WPBcDBCWKcDHVjCGdG+wvSYwF4mxOEexiG+XQikTii0Sl7kFCfgAihRWVBWA55/iZeFJ8FHPdW0CN8ukk4FWFlMpl/QgidgBCaPzw8vFRV1RugKD4jCMKOoBf7PhbmOMfzrqQoO3hR3MoJwjeDlIVZ3YHfhVyGGGYx4riTIIRfEyD8E+D5t2iGmVIujQuTF4S3eFH8BS+KPxwYGFgyMjKywDTNpdls9jxBEG6hGWYXxTBjhJ86sT+5QFl+gQFAJwiiG8MmAg8HUy5BQ75kMrn0tttu+xBBELf5Z2SOhYh8qvnipHB8jON5R1HVlwzDqBiG8fngORKz9H7rdvG2tXDhL+LohGI7+6/ZKPl0vo3ekW+jvMCHFfZdBQ5rY0WPk2+j3XKMe7kaE8oDneLnt120bWGg7Rwov9V0SCQS8xKXXbZg20VwYW8Mfqa3U5RKncIT5Q7OtSMpx4z0OBMtmVOTTMJMFHezbeSeXJR4GbXRcOs1xbM3x9HRCKEzKqXSLZZlbZVk2aMZZkrCImrOR4dmGFeE0JMV5TeqrguCIPzjHJ3EEmAi/YAgDlclqVtWlE1+tHNKX9a0JiFNZxBC/2Sa5nJ9ZOSwXKVyuiAI32No+hUWgHf8hV5fmI0mQ8rPLRJE8c8ihICXpEgoh+lgV/rX5QIhXKKqakzR9X5Bkv7on+E3LWHVi7Jr3UH/SDMMXq1WTzFNc2mlUllWKpU+oxkGDyVpjAGgXro1hRlVlxfNMHtYln2cZdmbWZY9f642OAzD5vnXXpRKpY5nGOZGwHG/5Hj+ZRYAdyq5BMSLE8S4/353yLL8kCrL3x7xy3VCBwv/bTcYENYfbhg57JFrMu/vbad/mG5NvpaNELuzUcILipcnEZafeJluTTq5dtIpdYI/DHXD2+5cqXwK8/O5DrLpg2HYhC/Ow7AWK26dY69K31jukkZKMc4JCMuK9jQSlmfVOqS6djQ1no2mRlE7Xbh7TfbSLWuyJxaLxbNLpRJrWdbjgih6FE3XTcIGDctN4fh4EN410ukt2Wz2W7lc7j1hOR9MeTTKBcOwFsMwPm6aJqMoymNCrZPBzAmLZTO5YvESs1xeXq1Wj8xVqxfzothDUtRuqna2YjBx93Ysk6RH1ByzY4DnH5dU9cvpdPoDjfc3V3Ixc7mLrVzuFihJ/+MT1r6DKrUDG8ZwgnidJEm9XC7/I0Lo2HK5vByVSqutTCYX1sinIawgYuqRNP0GRVF38QxzeUXXl4WrGg6mTLCGJFNJki6XZDkLJempkC9uqvlSN20Bx+3ief5pURR/hhA6dmhoaDGGzUInh3An0ZE4OuLBq3MXFtvp283Wnl12JDWeieBeECFs6O7p2pGUm4nint2WHLPbk48NdLL/54HVtQ6ECWzvAuKDgbofBMNahuLaCcWrcxf3doDefBu924rg42Zr0q337gp3RI3WmgNakaRT7GCc/k5h/X1xq/WeTu09xWLxg6VSKW3a9h/4WuFqkBTZWHvm4gRRJyzTNHMIodXlcnn5gcxHmQmCyYdhWEs2mz0v19t7kyTL9wcm3H58ThMmIcNk7VLpY2a5vHxwcPCYUql0uappUBAExyfyqckqdPgFx3Fv8oJwt6Zp/zI0NHSUf4tzoXlOio6j/v4zcqXSlUAQNlGTy1OmJC3/+ZwUjr9DMUypUqlcVq1WT6lWq6cUCoWv2rY9FBBWkJMWlq+/wTk0wzh+W6AnAc/LEMLzIYQLD7YswginUGiW9RHDNH8MJennYc2TJEmPDBEwThBe0C2XZtk9JEW9QjMMPzQ0dNrw8PDSQN6zR1hd+rIH16BPl2MA2JHkWD1/qTXp2q2pyYTVWjtaK9dOeWb7ureN9tvuK3QRV9x3zUQGNzY32kS9pGegAy4pXWedXGgHdL6NfjHXRo1mIribbl3nBBpjuCNqrb1zyinHgDvYDbfcd1V2zQOr82cWi8XzSqVSwbKsvwSENVWOkU9YtQkoCJ6u61K5XP4cQuhYf2EsOBQIq1Qqva9YLHaIkrSR9TP2Z+zDChHWwMDA8aVSqduyLEtRVc8PRtRN5TBhBXk6HM97oij+SZKknKqqF4yMjCyYC3kEmERYCJ1QrFYvZhgmTxDEbtJvGDgNaYX7po9xPL+hr6+vGyF0hi/fH1mWdZ+iql7QuHAqwsIJYpxmGEeSZU9WlAdlWU7IsnzGHGlWdYQ1T8uyzsr29q4RRHETw7ITDREJYhJhhTYmj2KYcZwgdpIkaebL5XMrlcqy4HtnjbAe/nz6uIfWZDsGugQj30a5VjTppSPrPLs1NUFYE0drOZko4fZ2MJ4Zu/1lOfbfA0rslgtRHM33v3rOCCu4LorH5zORmxeX2vkfljv4R8sx/q3eNtqdMmM/Wst6NyMppxQD7mC3dP99V+Vuun9V9rxyufyPxVKp37SsVzie34uwgskXnpAURbkQQrpcLl86NDR0lD8B51TDCiYgQuiEfD7/UU4QymGn+3Th9kmERVFZ27Y/Zprm8mq1emK5Wr02l8+jtGl6gOPGk6nU2FSmcjKVciiadqAkeYqm/VIzzZTiZ4jPJcKEZZrmUoTQqSRJ8jhBvErT9J7g6LF9aFkOw7IelKS7K5XKDdVq9Zx8pXJmb6GQSlvWL6EkBYQ11YESkzRyXdfXp9Ppr6bT6VPner6E5VKtVk/s6+v7Z4ZlEU6SuwmKcvyM/OlMXI+qPdsoSdOFjO/zxLBZJqxta7LHb12TXTWwEmZQO+P6Wke9Qd9EdLDHM1t7nGwUdwsx1st2Jf9orbrNyq6647y5MAOngO9D8+aheHz+QLd8U3+3fE9/F3y90M646dY7xhp9cnsRVpe09f54/rv3decvmERY3NSENcnRXOusOSoIwrpisXghQuiIQ8EkDAirXC4fVywWL+QFodjoJJ+J0z2Xy11imubyUql0cqlS+WIml+vTDaN+iMJUhBVoErKieGnTvK+3t/fHuVzudAybOA16LhDWZBBCiyqVyjIAwG0syz4NOG4Xs4+aSL89jMMLgquo6n2lvr6vIIT+oVgsnl0oFoFpWb8RIfSCkp/GNjZhk1CE0NMMo5zt7f0CQuikuZ4vYcKqVCrLisXiByma1nCS3EHR9BhBUZ5/0vRehBVYGwRBjDEsW0EIfbpUKp2MYbNMWA9cby5/cE12zYZuubfUAdxsrRbPDXqjhwmr1h8dd4sx1kPd+BOZVesEFFt3zizJ629EkJNVy9rdFDdv2HilPjjYLb9SjLGO0XrHmBntcfZFWOu75Z/ftzL34wdXFS+sE5ZpvcIB3qOo/RAWRY3jOP4Oz/O3ob6+84eHh5d6ntcSVMnPhUTChLVx48Zjq9XqhwRBKMyEsMgpooR+WsOphb6+r1qZzJCqaV5QP9iYn9aoSWQymU2lUunfS6Va+dNcBiMwDAsT1vyhoaHFoih+XxDFX/CC8BYLQJ2wGiJ7dcISRNFVdf1+VKl8rdjffx5C6JxiqaRYlvWUKIrTElZoQ3A5nvd0w8gVK5WryuXyciyUXjAXQtlL80ynTyVJEuAk+TLNsnsomvamqS+cICySHAcA9COEPue/69klrK1rsic+dFXvFzZ1a6W+mODmoqSTbqgf9FMC3HRrj5OJEk45BrxcW/KxdOutjP65W8+eJXn9TfAwzG/tHJ+PYRh2/+r8tXfHzdLQSuWlYox1tBV3jNW6jiZnTlhFn7D2YRLWFypBODiOjwGe7ylWqxeikZEj5lrFDxNWOp0+Lp/PX8Dth7AmOVEZZpwgiDcZhrGr1erFCKETSqXSab3F4jdN09ysKIrH+D6sqfw9QfRU1TTPsu0N5XL5JoTQqdgcL0xssuuiVhUgy18XIXxQhHAHC4CbTKWmLOIOE5aiqvf3Fos3FYvF84oDAx8slcv1IM3+CIukKBdwnCerql0ol1eGW/fMlVwafHuHl8vl5RRFESRFPc8CsDvoAxfWpueEsLZeja4fXqkWKx2cm20jQoQVLslJuX5nBqccA16+NfW4+dnbQPqzP/vALMnrb0IjYd1zjXXtXfH0uyKswS75kQeu7P3xQyvzHykWi+eVi+WSZdkvTkdYoZdUbw0CZZku9PX9M0Lo6EOJsMrl8vJ8Pv8xURQrvg9rJoQ1RpLkawzD6OVy+YJyuXycXSqdhorFb1i2PRw4l2dCWHo6vdG27Ztt2z4NOwQJS4Dw61CSHoCS9AbgOHe6rhONGlaxXK4RVrH4wWK5bJiW9fswYe0jqOECjvMUTcsUi8VVhyJhmaa5nPgrCIs5kIT1wPXm8q3XZK4eWgnzxQ7GzURxt563FA1lhvu92rMR3C3FWK93Bflk7jMpmL0i9cG59EdMeia/OSCGYdidVyvXD8eVvqGV0ssz1rBWyo/cH8/+10Or8x8pl8vnVsrlrGVZzwGe80KO2L3SGsLtRzTDkPOFwhWhRn1BndxBR5iwSqXSaYVC4QpJktbvKzM9ICyKpj2GZUdJgthOUZSo6/oHdV1fVq1WTylWq/9qZbODjSbhXj6sID9N0zwoy1s4Qfg2x3Fznp+GhQgreEeiKH7Lb5i3I9wTfwqTeTJh+SZhuVz+QLFYlCzL+p0QMgkb50tAesHpSbqu5wuFwtWHmkkIIVyi6/pJOEHQOEFsp1l2dH8mIXEwCGvbmuzxD1+Luge7odXbTrl2FHfN1p7Q2X+pMGG5mSjuFjpoL3N5z/P6J36K0p+87UOhKOFcInSQhNfSf6XwlcErxS2DXeJrxQ7WSbeuGzMjyf0R1kMPXtX7na1rih+qnWDTJ5iW9VteEDyKoSedALNX1AcAR9E0TzdNZGUy12az2RPn2okaJizbtv/BzuX+FUrSffvJwwr6HLksALtJinqWoCjCtu3T/IjaSaVK5YZsNlvWDcMD+3K6104OdiRF8XhR3MoAcCvJ8++fo8z/MOrXhxAutG37KMAwPwEA/JYXhJ0sANNGCYNSGwCAJ8vyvahSWZsvl8+tVqtnFYtF2rKsx3yn+16JxmHfXpDWoBlGNZvNfskqlQ5oH6mZIExYtm0flc/nz8RpWsZJ8nX/jMNpo4T1ZyPJPTTLlssIfWI9Qidh2CwT1oNxdOxD1+Yj/V2ikokSrhXBa22GQ3lY9YZ9rT1uJppyeztIz/zsHa9rn7hlk/GZn30cxdHh/lfPaVpDvRg6jhYVu5nvlruZbX2d/JuFNtpNt/ppDQ0n/QR5WKUYcAe6pfseurr3X++No38olUrvLxb7brcse1swAYPSnGkJS9c9RddHNMP4nqIo7wtqwuaasDzPa1HT6Us100xJsvwox/P7JSy/P9NOimGewGn6lkwmcwzDMIvL5fLycqFwdSaTyRv7IawUjjsUTTsihB7Dsk+kKEogSfLcudI4A4SjhKZpLs1Vq6cwFEXTFPUCw7Kj9L579rsESboMw7iiKN6FSqXr/aqI9xeLxdsty3okKOVq1DyDvw+CEbKieKqu36kZxndM03xvqFxpzgnL91d+lGLZHE6SQauZfac10LSDk+RuimHyA/n8J1/yLQAAIABJREFURwb8Mwtno7Z4opYwjo5++OrCJ4vtLJtu7RnzD3OYlOleJy2/YV+mjfCs1p53rBU9Py+1gu6RqH5S8L1zJOx6vZ5+g35Y+fPguHwslcp34H/ubSd356KEm474iaPTEVYHcAe64Zb7r82tfmB1/sy+XN97yoXydzKZzJ2Kpk4qfp7OJ8ELgieI4tMihJokSec1dIic01ILURSjkiQN+CfqTNldIbygWI5zeVHcwXHcVo7jvo0QOhwhND+bzR5fKJc7TdM0pzIJGydy4KvpSaVe+enttw+mUqmPIoQWhe/zIMslvDBbEELHor6+80matlM4/g4xUX4yHVnVw/eAZdcXi8WOUqn0PjQw8N5iX98PrGz2bllRPJplnVRD7ak/VybVnoqy/AtJUZJ+d9HGHu1zJRcM9fefUahWV3Ict4EkyXGi4eDV8HsOB2lwknybpGljoFg8GyF0NIbNMmGNxNER960uX9AbpX+Wbr1jZyaSGsvUTlh2gwXeWJ5jRVJutg0fRx3Ubwe6xW/d1W1d0PjABxPh6w6sgccPXa1cWOhk7N4Y9VY2io/55xJOyi2rp2u0Jl07knR626jxSowfuPf63hVbry2dhhA6qYRKN6TT6bKkyC7N7q3ihwjLI/3aMMBxbwCeH6EBiAbtU+Ygg7nelSCRSCxKJpPLaQDW8jz/OMdxrwUnRE+3KEPFrK9IklSVJOmG4ADRSqWyrLdU+oyq6xwvCOOhw2SnLPINulikCOKdZCr1c47jVlqWdXJwn3O1wWH+gRGmaZ5hI9TNArCRnNzjfa8gQkDAfvR0J03TvX6A5aRctXpKqVT6imXbg5qmeew06R7hDc4/rfs5luMQz/MfM01zaej+5pSwMgh9OFcofF+EcCtb6xU25dmFvibt0gzjMiw7SjHMiywATC6XO2VgYGAJhs02Yd2gHzbSVTm9t436vt267tVcG7471x60Zdm7W4PZ2uMaK+5wUBvl9nXxz2+8UhY2x5W2+o0lDnr1vX/d2vPcudo4c9Mqec1AN9xS7uTdieLn5KQawolTopOeHUk61ork7nyURCPX2h974HpzeTldPq7YW4wqiqKyHAhODt6r1W2juu+3mHkaJ8nv9PT0fLh+fwexK0HYF8Jx3BG33377hRRF3c6w7E5yH+1CgmdIEYQDAHAhhM/rui5YltUWfLd/DuKHOY67HSeId0iKGg/7dhqjamG5cDz/jKqqP8hkMhfNhVxCqJ/raFnWR0zb/i8oy49wM+jW4C/MPSRJvkrTtJxfv/4DaPPmoxFCJxQKhbhlWVnDMDzAsg7up0ZM9V0BkRMkOYqT5DYAQLeu6yfNUbcGDMMmE5ZlWZdZmUxaVtUnBVF0yVpfLKcxCOGvi/oJSJwoPilAeAuE8OhAk54Vwgp6ucOL4MIt3eXjiu3Ml1GU/C3qIN/It5Oh9jLJSYRV79TZRrqlGPtGXzd3T7WL+8bwFcml2y6CC0PHvh8s1DpJxuPzE5clFlS62Mv6Ojmp3Mk9UewAfiPCnqkbEa5Iutko7vW2k6P5CPVCIUqDe643z7j/RvVIxKEjiunihyRKuRUkuR00ye4JfDzhQt+pfD+8ILwMOK7McNzn/WOV6u15D4ZAQoQ1jyCIU3Ec/wrNMP1c7UTm/XVODQjG4Xn+KU3TfpTJZP4p+O6hoaHFCKFTIYTfBBy3nQVg13RpEnUC9OUiQPiSLMtIkqRrA//eQe77VPdfJRKJBQRBHC5JUiw4Em1/7WWCYATguF0sAM+wHLfOLJeXI4QO13V9Waa391OSorAcz4/RNO00mlHh4WvqDgvAOPf/2vvy+DbKO2+ZXCRAKEeBQguFUgjL1S4LbFu2pS1LbFmS7QRzFVpg23Shd7dvd7vbbdVyxpZGcz7XPHPq9FiSDxknJgnalqMc6ZFS3pYC4UwLIVy5D2vm/UMz8li2nASSFPbV9/N5PpB8FGnmN8/8nt/5/QHwLM/zt3Mcd1kg8DdhsagN57Usa26mVDqeGsYtRFV/BxDaxDeYZeB7H8aFKrHhm1RRfiGr6rcty5p7QEMi3mAId7zX/OEwXDoUlv6nEBH+0heq8mGZUwj83LHvrT2VbBtjWyF2Zz4ivJyP8GIueNdZ1hX4aG881yFSWi0Blyudb+PnZcL4+EJY+JdChF/XH+Je72vn7Op99E4lImzttY3FPZW+dtYuhIWtxbD0+4F26b8f+VZqodVtzbWi1txib/EEfJd8K7wLPyOx4G2+2jQ8I4Oke9JsBxA+CyGMiaJ4mqIoR3kbInDwN6Hngh7G8/xClmUvjTMM5Xj+TwBCezrK22leJofj+e2iKD6uquoNlmWd7n25ZVmzSqXSAkrpjYTSJxHGb0zq5m8gF9fF3IYQ+iPE+A4I4QkY40POrOkpLE3TDscYnyoh9B2A0HoJgM0u79NU+Uy9j7cRxo8gQn7g3sNsXCotUJLJs0UAfsJy3GaW42oHXCMFyCQS46Ik2RChTYIkjbA8/zWLYeZ7swcPkUwCgYlyisP4VGphNp//B6pp9yBZ3iyI4m7fiLhGSZpxoUod/apmGDnTNK8NBCbHCg/IVToBp8WJVnnRVy5RPr9yCdUGO8FT+YifInkKgV/1pW+N2Zm2+Hh/mNtpdfCrMh29Nycjy892AtV2lEPRX1jLCgaihw10Jj5gtfGfK4YEthDhtuSCzK5Ua8yuJhEmD5+YUFi941Y7Zw92gNdHOsjK0S7la+VoebYzcfrPVeJKRGX0USzRFyUIPRO4EcuBF8salwDYDiFcBURxmSRJ5wQCkweQHiRMGrYQj8c/2dvb+93e3t7fxOLxrYkJJoKGlpUbW7EhhC8jhAqEkE/7YyueZaSZZlDR9VFM6YugKpeZON1r04QkALZChAZFUQyJonia1750KFwgv6sci8WOj7NsRJQkBWG8gxcEL9PZmCI5Fqu6yoRspKpqaZp2vefWYozn8KnUQgjhLRIAz4qS9PZ0wznqXnSPfmcngHADQkjSEPq4hfHRgcChq1Xzy8UwjFOSyeQ3FVUdxYSMu9nxvVEk24Ig2BjjF0zTXN7f33+5+73eYNsDpLCcqsIKBAKBcrf2ifLVxr8PdkiP9IUmLJP6AQ41peWWPeRCCceK8E/3d7KZ/i6uY6QdHGN1R+dW+amqpRMH5GLrrz0wQRhYCkcXjLRL5xTaxf8shoRyf4h1Mm1x21zcY9e7gX6qHKO1p5INJuxCSNiwspOCVUv0WizO6rZmBZxAi8EYlxiMcSeWyK9FACozuAyTXk5BFG0AwHqZkCKl9HpZlj/MMMx8f6lB4MDJpjb1OBqtjrMyDOMUhNC/8pI0yCQSG93424zX7tHkIIxtRMivCCG3S5J0ptcP6Y+taKnUP5qp1IxlEpOUeSJhM1W5OAChP2CMBYTQF03TPMKzKA5mAN5//YqiHAUh/KQIwD0iAI/WdzI0eq6MW+XOi+JzsqLcbZrm59zvPqxcLs+ORqOzMaXtMqUrMCEv7G04h6cI3Kk5uzAh/yNj/A2E0IV47do5/sPnYMnFk0k0Gj3MNM0TVMO4QtO0NJHlZyQA7Onk4oVD3Hiup3R3QYzXGcnkV4vF4ll+mR/Qi/WC1Wu7rVMfvSYX6g/yo+nWmJ1s7XFXw1FZtumS+fWF2V0DHdKbQxH401Vd8jlrw3iBE4ge5rgDVA/YBU+gxfG9PGNd8IRSBwoORcCaQlh4M9fOeq7rpCZuv7JKtva69WYxO90Wf3pFB/3eI9flLwgEAgGr25pVjpZnOwGnhd5BT5PvkDsEVhrleH4PM8G82PAk9jahBMAeVdN2qLoOVMO4Ip1OH+NVVh9Aq6IlGo0eVi6XZ3uZPMMwTtF1/YuKrvdjRdkqiOIeL5szTZXyhAURj1fc9iKHyHJKluUlqqp+0DuB/S9QPp//eD6fvwERssajq2n0wvtdIzf4vhUT8jIh5DuKopzsTTU+mGO+fHHEADbNUwml1xJCHgHuvEamGouZxHfmi1PW2q/uWb58z1133/0EL4q35HK5jwUCVTfZk306nb4klUrdrarqbzEhDZld66zPigShgxB6lSD0K1mWr5PK5SO9+N7Bqn53nOpAEfd3ApTSS2Rd/y9F056FGNuNsr9+hesdzqIkvQ0gXKMoymVedjBwoLOdTsBp8Vy3td3W0Q9ckzurEBZBXzv311w7szMTjNnVdpbJQ0lro77cModMe2I8HxF2DXRIq4ci4EcjXfC8sRvNIxzXAjpQgXjHrWavFr06LWsvwnOsy6UjixGhuxCR6EBEXG+FuJ2ptridrJYyONOUZTjJtt5Kui1u59oTTl+I3WS1c/eVOlC43K3VKnOt7urLg+/BR6Pb0cdFUeIEAF5wOcz3Oi2Y8QLXEI5jQtYpikJ0XY9omvbRmjXhO/X3w+KqFsl6LKvOxOw60zSPUJLJs6mm3SKraj8i5M8ShLu9QHt8htHjiWovpC1J0jaM8V8xxv8ly/I53uh4/0kcCAQCpVLp+IGBgYsgxroAwOscz/tjHdNaWT7rczfCeCuAcAhg/A2J0jNHR0fn1Vlx736/1F23pmmHp9PpYxRFuUmmNIcwflkUxd3es6xPpvgtT6+eLMGyG3pisQFRFD/r1hm1+AZqtMiyfLqmaUt4nh9NsOwuhmXH4774z3SHRYJlq/VqorgNY/wKIoQiWb5KkqSTPGV1IDOHzuR9d1g6nT5GNs1zqKr+mCrKAwDjNwVRtOPxuJ1okPmNM4zTG4tVWJ63MSEOluXfyLIc0zRt0cGMwU3KFpbCeEEhIv1bISz8Kh8R3sqFEpVkW+/41MnP/vmEPXaqLW73hTknHxY2DkTAmsEOcPNIFzxvbRgvsLqjc7u7u2fVBeL3R/O6VezeqlpuT3Zbc4ciwsn5oHhpPiKK+YjwTH+Y255tT9iGb1R9vcJKVcd+VTLtTKUQFpxCWHiiGBHFoQi4YLSNnxeoUwbRaHQ2z/PzIMa3QoRWQ4TemKl1w/dAPUvLARDuwrL8rKJpvGEYV6VSqQ8PDQ0dFY1GZ3e7J7/vAe9NLjUF5cWTotHobGpZx2qp1PlU024hipIllG4BEO7mBcFO1AVMGyisijs+/mWM8WpCyFIvoOzJwldP1qJp2uErV648FsryTwFCT0gAbGnUHFtf+uHFySQIX0IIDWNKu7Guf4zn+XkY4zk+i6J+7et+CfifI8Z4DmNZ82VZPl1V1S8oiqIRWd4gAbCT4/lJ3FfTlar4e0VFAB5heH5Si5H/+d1zzz1Hx+Pxs+7p6UE9vb2vMiy7K+G6VdNUvdeWx84KAHAgQk8gjDFC6IuSJJ3kKUS/pbWflqi/3q3Fp7DmplKphbKuX4RV9euyoqxCGG93GUZnmuJdkwsvCONUVXermpYzNe16l7TvoPZEtnj1U1a3NSu7JNHe18lJhS7x5b4QW2PqnMgS+pTWhBKzzbaeSl+I3VWMSK8MRMCaoQj40apr5HNGJuiTJ1qCPO0+g9XlWX+1z1czbAEnEGh5stua+1AXPKHUiTsHO5A20CH9Ph/ht2eCsT3J1onhqVNGe7nuoN7aU0m3VXsiCyGhOBgCN5dC8BRrcsxg0umsKMplsqL8HBPynASAzVRrUmZygTxLq8JXSwS2y4ryom6aA9ls9tvpdPoSN3s4u9GDrVcS03yuxbKsuaOjowvNdHqxkUz+nCrKAwjjv0oAjHM8X3FPyJmsHs+CqFBFsRVFeRBC+E2M8fm+l8R/srd47hvGeI5mmtdSRcliQl5xaVn2FuNzXGumIgGwA8vyi0SWBwmlt0HDOMUN8E9iUqizQqffL3XWlP8FZSxrvmyapyuKchOldFiW5achQjtZjtvjurJTZFL/DEVJsqmiOFhRVFGWg6IoHhdwnJZuX8mK4zgtGOM5GOMFvfH4d+Ms+4AE4VvuATdpIEWDfWMnWLYiArAFYfwnjDGWq5bWkS7fe01ZefHKvVjmtdhm3ecDgUCgJZVKLTQM4xJZVf+LEPJbCOFGQRQrjOfez2CRM4mEZ3XukCndRFX1x1omswhX3cGDmzDwWz/JCHt2X1filkKH9Kv+MP92Jsh4LqHtL7j0x4bMKhupnQkydl+I3ZUPCxsHO6RVI0vwf48sIZHV1xhnreq2jl57UXXsVZ2bOK3V5V1TzZLo7p619iI858FI9uSxDvXSUge6eagDkaFO9Od8WHgr156oXmNNufoU1sS12p472NfObiuE+VeK7cIdI+3golQbv3AaQdeUhWEYp8iq2kEIGYEI/UWUJHtaF2iah8t67haEFSzLL+q6PkZV9S5M6fW6rn8mnU5/vFQqHY9LpQX+OW7TKKsWL6iuadpJpmmeQyn9oizLNyuaJimq+hBA6E1BFG2W42rUNzMpVbfquiJK0jZMyHosyyKE8JMY4+Pd355u49WeVTqdvkjRtP+DMf69KEk7fJm2GQPYXhGmBMAOiNCLmJABiPG3VVW9wjTN0yVJOtKz7vxKyP/CTdovE/VVNcvYdQFPU1X1c7KqfluW5Rwm5BWvwZmpq96eRj7VA0cQbIjQW6qmPaPq+vdk0zydsaz5nkvvXYv/gIkJwmJWFDmE8XOiJO1hEolxr/B4OrfTLxuu6ppvQQg9QQihEMIvqap6aaFQ+BDP8/Pqeg7rD7MpcvEprRbLsuamUqmFmUxmkWEYIVXXbyeErEEQ7hBEcU99CUODa60pcYjQS4SQMUxpd2p0dOGyqmI9NP2QTsBpwRfhOfkIe0EhLJrFiPRcMSI5mXam4vXiTVJantU1obgqZltPxQqzdiEi7hjqRJtGu+TUmiXmTau7jLPGrqylx+tRm7jTqIZr7UV4Tvly6cg1XeYXxjq1nw52oEcHIuCNgQhwMkGmYrQur/gtwSnX5/UNBnsrxbBgD0bEVwYi4kP5MHe11c3Mj14ebTQuvbYpKaWnEYR+TCl9gKqqw9eNcppGWdWUQszdrIIoOjKlDpHljZiQR3TTZNLZ7I2FQuHvtXvvPanbDUBPJyQvYJ/NZj+SyWQuSyaTyxRFoQihpwghb7lN2k6cYRx/VX79i+hXVrVhnoRsTLBsIRaLfSngq+Vq9Ly8ZVnW0aqqfg5COOoWzE6i4tnL71eYRKICALARQlswIc+rqgrS6fQS0zRP5Xl+3rT7dGqsa4q8NE07vFgsHpdMJiO6rjNUUZ7EhGx1B4pU6t3ABs+twiQSFUyITVX1GSOZzOip1Be9Z1H/nPwKFZvmqUiWryMYPyZJ0nZfHHHG3/Sei+eiY0Jewxj/2jCMaKFQ+Kw72KGhRb63WFcqlVpYKBTOyGQyXzVMM00U5WWA0DgvCLWq9ems8PrnlmDZCibEJoQ8QhD6AULowsABjrXNCM9ds7q7ZxUWJz5UDMEvDXaA3FAn3N0XYseTwVpcyE7Wlwi0TbJg7FQ1oL2nPyzsKEakPw9E4H2DESAOh/F3x5Zq4TXdxiWPdlunP9pVPO65m8qHu5dQ23hrL8Jzxm40j1h7Q+FD9y/NnLvqKu3ywS705UJEiBYjIFuISI/nI8Krfe3cjkwbY1frraYqqzouL9ts661kgsz4YAfYVeqEvxwOw+8NBKVPlC+PznYauxy1UzORSHwAQvgZLMt3YkqfkwB4m+f5CsMwXlXzFKXlr9Fi3PgNLwgVUZK2AwhfJbK8DiF0nyAISQBAL6X0h7qu35rNZm/K5/PX5fP566xC4fpMJnOzruvfgBj/BycILC8IOURIGWH8RwmAtwRR3MnxfCUxQy2RfwO63NxVVgYIN0GEfimK4jKGYc7dx/7Hlmg0ehjP8/NoMnkmUdUfyKq6iirVRnEmkWjUllJvwdgcx9mCIOySANgCEXoSYzyCEIpjWb5VNc3F2Xz+k6VS6dSBgYEPeLPuJu2XtWvnDA0NHTU4OPiRYi53YSqVulLTtK8RQu5BhBQxxusAAG9MVwRZn/maZBlznC2I4h6E8WaZ0uFUKnVVOp0+w7v3mfbLckU5CsjyRQCABITwNwgh26coZ3KX/fV8tiBJ2yFCrxFC1iqy3GcYxk8zmcwNfYXCZ93JTh+yLOtI3ySimlxGR0fnFYvF4wqFwhm5XO7idC7Xoer697AsA5nS+4gsPy1K0laO5+39tYxFSdqBMH6BEIKIJF0MITyhLhF0cOGnnLG6mfkDbfhjpS7y/VIXejYf5t7OBuO2164zg8Jykm29jtHqNkgH406uPeH0h/id/SFhw0AEPDDSRcloh/yfpQ705fs6lStXL9EuHluqLSpfl1n08HWZReWl2qKVXejCkQ7p06UO2FXqwN8odZLlgx2wmI8If+wLc29mQ6yTbWecdFvMrres6jOCtSnPi5fbmSBTyYf57aVO+Py9XVhcFdTOX7mYHut4SmkvJ1e5XJ4tSdKRhJAQIqQPYfyUBMBulmX3MHUp4PqTydd35dGu2IIoOm4D7O5EIrFZEsXnZYx/o6vq/aZplrLZrJXOZq1kJpM3TXNEUZRfQIzXcYLwcoLjtoiSNC5KkuOejlOshnpzvq7Yr8Lx/B6E8S6I8WOAkF4gyxdYljV/fxRWIBBowZZ1tGFZn9KSyXtUXd8IINzm8sE3jGdNUhATBZSOK5MdEMLnMCGrVF3nqKr+QFXV61RV/YKu6xdpmcyiTCazKJPPL3Jdm09qmvZPiq5frWna9w1NYymloxCh5wCEmwVRdDier1HeNLKs/PKJM0xFlCQbYbwFYfwEofRnmUzmRIzx3mI0tZeW5/kP8jx/FYRQl2V5iyCKu2aSyRTFlZhgu3Ct0K2qqv7BSCaLyWz2Ts0wbiOEdFFKP6MoyoWapi3KZDKL8q5czGz2H1Kp1JWmad6om+aPDNNUqKI8ACB8FSC03a0/qx2m+3BNXrX/OMR4I8Z4FGO8jPFV5x/yZnbHcVqcWrsO+dxQBMWLYXFdfztnp9ri4+7g0UnZwlogfrK7WJ2q3NZrp4Px8b52bmc+Ir412AE25NrZZ9LB2G/zEWFVaQnOr7xKNX55TVp76LqcuvoqQx/tItliSBzKtTMPZtrjTxbC4vPFiPhaf5jflgnG93iWXLKt1zZbe6YozEmUOG29jtnaa+uLe8YHwpK9cqny1xVLsT66RLrGulw60uq23CLXmQOEntKyLGsWpfQ0QkgbkuUcxPh1UZJ2+watNvT96wK5tlt5XmFZtsLx/LgkSTsghFswxm9ijDcRWX7VXRsxxpswxm+6QxJ2shw37v37xGSWgb2d3jXLCkC4DRPyCqF0uaIol1FKj/XqlfZx49WyTdiyjhYA6OQlqYAwfhZhbLMcN97INay3Rt1MZsW1bMbd2NYbmJCXeEF4KsGyjwMAVsqy3J9MpfSsZWm5fF5LZTK6qmk5hNAILwiPcjz/Z4TQSwihTRIAOzien9TsPUNpR00+nowkACoypc+rut6rJZP/7PXH7S2g7Cl7nufnCYJwsiRJX4cI/Q4itAkAYCdYdryR6zWNYrcTLFtxLfNxgNBWhPFrmJDneUF4gmHZh0RJGiaUZnXT1HK5nJbP57VUNmtqup4nsnyfCOGvRUl6FhPyF4jQW4Io7uZ4fjzBcTbjs8hnOOAcd7/aHM/bAIAdRJbXaZr2HS2d/kRdycshVli+0yPbIX1kIIyvLIYEtRjmn7PauW3pIFNlP6iVDUworCojwtQCzVRbzM4EGTvXztpWiLPTwXglFezd1Rfm3hjoBH8Z6cLPrVyqrF+1VHt2xRJ5/XAHfLEQFl7JtjNb0m29e3IhttLXztq59oSd9gpC3e+dtm1owsqy3VmElUx7ojIYgRvGligrxpbir4wtFRZ5Qf19rBGrBcA9+lhC6W1YlochIRsEAHbVNxbPoLBqSothmFqti8vyudflmfC+39qn05Fx6X15QdgDEdqOCfk9lmVVUZRIJpM53u2u31/Kl9p+icfjZ8VZ9suQkCIm5FVRknbW0880UliTZJJI2J4s3OTGOMtxO0RJ2oQJ2aBq2nO6Yaw3THO9puvPyZS+BCDcyHLc9lohoyjavCDYjZRVw+LZCdYJWxTF9RhjSzWMjmw2+xH/HpjxHfIlAKLR6GwR40sBIbcTWX6IELJVEMXdCV8F/EwKq04uk/aI26+4VZSkVxEhL1FFWa8bxnrTNNerhvE8ofQvAMI3OEHYyXKcI0qS7fZLOnX7p6FF7rO+qsoKQhtjvI5SKpmmeZlhGMftq1wOFqo/3N09q7u7e5bVbc0qBBM3FUP80FAEvNYf5itm6/I9RltPtXXHF9RuZOF4AXmjraditPaOm+5A074Q5+TDglOMiJNWISI4/WHeybYz7vCL3orZ2jtuzlBfVVNavoyg0ba8YrQuH8+EEpWBTuQUw+j+Qpv0QyvMner1Ie5vQavf+rAs68xkOv1lqusPY1ne3Cigu5es0CQ3JBaPz7jcz9iNguozfXecYfYIklRBGO8mivIqpVTDGF8KITwh8M4DprUMmWVZs3ienydh/G+QkEeporwNIKzE4vE9fn7zRvKoL7XwVmKCa8xxa8UciJADEar9vwRAze1zf2s8Pk2ldqNAsicjV6l7syYHGIa5OZFIfCiwn7VF/rYUZWjoKNmyTldUlZNl+WWE8U53lNh4AwbPhkrLLxfX6nIkAByAkAN9coEYOxKEjiCKjpcx9v6d1/Ewg1VXn5ipMCzriADYMqUVRdOInkpdSSk9dn/lcrDQEnCzdtFA9LDhMHNusZ2/ZSAMSoWw+EI+zFXSwbhtTGfpNFgpnxuXdEkA021xO9PG1FbaXd6fU221YLobzJ+mt3G6VWu76bX72hN2Psz/tdApPVwMSz8oLBb/fiiiHOU4bp3X/lfg18oLLMs6OpVKnU8p/SaR5X6M8UYA4XZRkvw9ZHb9Rpgppb23NVNQfYZN7sVCKgDC1xHGvyaEMERRukzTrLEmvItTssXvMkuEXIxl+btElssI41ckACosx1Vi1RdmXxXtlPt2OaQarmmszn1xkWv/pIwzAAARMElEQVRFvhzP2xhjW4LwpZ5Y7L4Yw/yrEIst6u3tPcJxnJbA/rs8niKfqwwNHaWqaohSGseE/EFy5x8mJlp39ktx7YtcWJ63WY6rycXbOzNlj+sVuBtbtEG1JOdPqq4buq5frarqR7ze2He4Zw4sfOUFLXzbt+ZZEenMYgh8fygCh+7thK/2h7nt6WDcn6GbUZl4dVEpX/N0VbH0VAx36e4yWnsqSZfexmzz+gF9MbJpgv6TXMC2WCXdFrezwcTugbDw+mCHWO7vFKKFsHSxVxz6LilwqqdntVBwARHFszDGyzDGK2RZfgoTspkXhN2JBgyW+2Bt7fX02xfl521QV1ltJ7L8GiLkQYgQizH+vCzLJwbeuWU1eb/4gvQuz9S5GOMokeU1RJbfEERxR3yiIHFf3dhJSsVr4G609lVJTaPQq0WQAOzSdf1Vqiijd9x113fvvPPOC2qWkttK9S7k0iLL8olEVa8gskwxIesQQlt4QfAH4ifFkw6kXOrjVDPFq3xuYIUXhHEA4TaZ0hd0XU+m0+kOd3r3IWPZ2B/U6qNKYbygsBScce8ScuPqTpob7SLPDHVCxwqxTjoYr5itvZMr4r3lc90mBeknKZ2eulXn4rXVVdi3xSb9hi/IP54KxirZYMIpRERnsBO+PtKBVtzbAb830Ik/NtrGL3T2v9WjoWwcx2mJlsuzMcYLqCSdSQhZrGhagqrqWoTxZgmAWgYvzjDjfutiOsWzL67jPvwbO84wld5YrFKLORBiU0rXG4ZRVFX1VkLIJzDGx7tFiAcys1OzshRFOUok5FxCyG2yLN8HEXpJAsDmOM4LsE+q/N6XF6nuRZ209kXR1yureJVzvSKKogMRGpcp3ZDKZDLpdPpfli9f/uGoJB05Q5fBfsuF5/l5siyfSNPpzxJKf4YJWYcx3gQhtFnXZWsUTjiYcvG5f54LaLMcZ0OEbIDQDoTxU6qqskY63ZHJZI73LPJ3KZODA8/KcgPUs1dfY5xV7tKuXbVUgyu65LXFiLipP8ztyoXYSrot7q82t01X+UxWNpOtrcYrNkXx+b/Lb1FV3cWYnW1nKn3t3O58WNw23IWeGF0q51YsobfdG1H+oS64fmAE7Uv/u6nd46mmtbpNpAOEkD8ACDeLklSrkWKmMen9Zvq+KCxvc033fSzHVV0Bnq9I1RaPFymlD2iaJmYymRtyudx5GOMFXrPugd543gtuWdYsTdMOVxTlQkrp1wmlJpblJwAAm0VRHOcFYYo86mXwThT6DHKrucee3LmqjHZgQt7ElD5ONU3J9PXdMDg4+Hfu7Ryww82TczQanWutXHmsrGmXE0J+oqrqMKV0vQTAdl4QbJbnK/XXuTcX7kDLhRcEWwJgK6F0A5bl1YiQXsMw2tLp9Gn+e3mXMjl4mM59uj+if2ZlB/1JqQv9drgLbR7uxE5fO2ubrT22sXj5uN56T8VoXV5VWo0UUS043zvNik1VWh61sdsKZLQurxiLl48brcsrmWDcHogAZ7gTbxvqRH8ZvUrm77/RXLyymx47030cANT6utw/HwYhPCGdTncomiZiQtbLlG4msux4VeBuAH3cDbrWAqE+BTaTBebVcvmD9OPuyVzhBcEBCDmYUkdWlBcJpaOEkNsIIZ/wX/TBrJnxB5y95mMznQ7qpskRWV6PCdlDZNnhBcGOxeN2LB4f743FJgWD99cC3dtn/bJiqvEqBxPiUEV5U9G0P1Jd/xkyjE+lUqmF/mcbOIAvpj/1z4+OzmMs69hMJnNz0jTzqqZtlCl1IMYOy3G2K4+GQfK9yWUve8ivqGpySbCsLUqS444f2yCrapmq6td1Xf+YZVnzA++RAPs+o0Z/7Dgt5aB20liHeunoUvK10S4CV3QpjxXD4sb+EGf3hzg7187aqWDM8WJcXtuOF7uqWkcuI6j3d7VVYwqtWWxma49dy0xWh2PY2faEbYV42wrxdj4sbCl1kXX3dsnJe5eS74x1y18Yu1b9SPkm7fCDTdlc36TMMMz8bDb7UcUwPi+r6jJN00RFUe5HGL8gSdJW0U3Xe2lml49pWotpuuUpNX/qX6ym8ndBhF7DhPyaalpWUZT/oJoWhhCe5/UG1vUnHkzUfitapb45VTGMzyuG8X1VVZOqqj5BCHkdImRLAExJt08Tl6qvxp7x731xnZrl6VoOtgTAOEToDUVRHlM0jVBV/apiGJ+SM5kTeZfm5iDJp5ZRjUajs/nR0XnJZPJst33odlVVh0m1g2Kz91xdBoxJ8TbGF/NqdP972Us1uXA8b7szKG0A4Q6I8QZV11dphnEPprTTjUUe/TegbX738DckO4FAy2gbP++xbu2k1V1a6+ou7c57u9CK4U7w7HAX3FjskLbkQok96WC8kmqNVZJtsUqyrbeSau2t+DN/ybbYDGuSInO/I1ZJBWOVbHtivD/Cbx/uwq8Pd8LnhzvRwyuWKtz9V+tXr70h+aG1y6pd44eQY35K4/To6Oi8kZGRY9Lp9BW6rv+QKkpWluVfYUKeI7L8CibkLQDhdq9lpNELOWVzuqOmhKqC2kIIeYNUCfH+IFO6QtG0nmQyeXUymTzbsqqFsYG65tyDLItAIDDhHnp/tixrvjU8fHoyk1maMk3OMM01mq4/RxVlE0RomyCK42x1YKf3UjZ8Oadb9S+ltxLVwtw9EkJbZUV5Tab0aVlR1hiadrdpmmFK6bEHg49rJrn4n4GiKEdlDeOTuqouo5QmSXWPvIQIeVMEYIfvHmuycf87yZWbTh6+TLX3OX+hccXdQ29TRfkrofR3lNJCMpn8fjab/bTXfB6YuRXp/YEqg4I1a7SNn7eymx67eql6xkg3bh+9mvz7yqVK33AX+l0+Ir5lhbldfSHO6Q8Jdj4k2FaIc3LtCScTZJxMMO6kp7h9MScdjDmZYMzJBBkn255wcu2sY4V4pxASbSvEOVaIHc9H+C1DneDP9y1VV953lXLnmmu07tVLjQvGuswTnuy25pYvLzdqZj7Y8Jc9zCqXy7PT6fQxpmmebhjGJUYqdU0qk/mJbpopRVEeQgj9WRTF15hEYjfLcRWO5x2O5x2vTUUQBEcQBIcXRYcTBIfjecctpNwmArABE7JO07T7TNPkU6nUN1TDuEI2zXP85QqHrCF1ZpkcFo1GZ7sDWT+Y1rSPW5bVle3ri+qmOSwryv+VENomArBHlCQHIGQDCG2v9ci97xndHL/cpCqvlC1KkiOI4h4JgLcwIU/qyeSQbpo/NlKpkGma5xiGcZzHunmIX8ra4VEul2crinKULMsfRghdqGjaTaqqsoiQsiCKz8cZZjfH8xVRkhzXQrT3RSYsxzn1+0mUJAci5P37XRKEryJZflQzTU0zjNs0Tfsn0zRP98gJD6FFfnDhcar7sm6B1dfJJ45dL19039XqdfcuIT8e6oTKUASUBjvgw0Md8MmBDvB8ISK+mmtPvJUJxren22K7U8HYeDIYq3grFYxVUsHeSjoYG88E4zuz7cyW/jC/qRiRXi51wKeHO+HaoU6waigiZe7twHevucr46oPXJv/psZuzHynfpB3uXcshnNwzHVoCPooNH3/UAsuyTi0MD/+jmU53a5r2HYzxnaIoYo7n+wEAJQjhKoTxLwghDxJFecitjn4IyfKDiJAyQGhMEMUhThDSEoQcIeTHpml+ra+vb3E+nz83PTJyTNRnVXnXEvjbbriaEvdfR6lUOqV/cPDTqVTqK4qm/RzJcgpTuoLI8mMypX/CsvwigHCjIAhvsxy3g2XZ3QmWHU8kEpWEa2W4azzBsns4jtvBC8LbAICNbrLhKVmWH8UYr8AY61RVf5ZMp7+czWYvzWQyJ3qV/YHAVKvnUMBv8Xp7ZNmyZXOSyeSZuq5fiWX5VgmAXk4Q8gjj+6mi/EaW5achxhtECF/nBWFLgmV3MonEHlcGlbo1znLcbo7nt/GC8KYE4SuYkPWU0j8gQh4EEA4BhCCm9IdGKtWlZzLnplKphR7ds//ZHUq5HFT4aWH8f1/u1D7weCR59kPd2fbyNanvrlqiSSNdeKgQkX6VCTJ/Mhff84rZ2rPZXNyzw2zt3VVbi3t2m609u8y2nh1G6/LXU229z/eH2N8Od8H7Vl2lpMrXGtGHv2Rd/9iS3MWPBa2T9uVa/pbwcRdNURoY4zkrLevYgVzuY5ZlXVIsFv+5UChcNVAo/EuhULitMDz8rcLAwLfyAwPfzBeL38gXi18p9vd39Pf3X25Z1idSqdSHFUU5qv43vZaQ92LMoZEVY1nWsZZlnZ/P55f29fX9yDRNqijKKETocZbjnonH4xsZhtkSj8d3xuPx3XGG2eVbO+MMs51hmI0syz4DJelxRVFGU6mUlsvl/qO/WFwyODh4fqlUOr7+Wt4Lrk7dHqnBtdJPKgwP/2NxaOgr/f39dybT6ZSiqmsgIes4nn8hFo+/EWeYba4M/DLZFYvHd8Ti8S0xhvkLw3F/hAg9qKpqIZ1Oi7lc7puWZf1zOp0+w7+HZtqv/1tQ08BeQN5xnJbRNn5euVP7wIPd1qm/6E6dv6pLuazUgYKFkHSN1c4ty7YnfmC1sz/pD/G394eEu7yVD3F3F9r5Owth7ud9wcSPcm2JbxU7+C+XOkHnWLf6hQeuT1/08A3Wmb/ptj64NlxaUDuhAgekXuagoP4krZESuqn/0VRqoWmaJxQKhQ8XCoUz8vn8onw+f25xZOS8YrF4XrFYPC+fz59bLBbPGshmP5rNZk8uFovHmaZ5hBejqie5ey8qKxf+5zRpTqBlWcdaw8OnZ7PZT5qm+TlKaRhjfL0oirdygvBDQZJ+KkF4hyRJdwMA7vKWBOEdoij+TJKkH0qCcBsA4HpKaTiZTF5uWdYnLMs6feXKlcdaljW/jgjwPbNf/NfkJ+izLGt+ZmjoxOK9955VKBQuNk3zC4qidBFFuQkh9C0RgB+JovgzEYA7/TIBANwlAnA7z/M/EUXx+5IkfQ1g3K2q6uJMJnOZS03z4VQqtdDbQ/X79G8tk0OB+qEKgYBvU5Qvj862PmXNL1+XOf7BbuvUB67JnfVIt/V3v1yaucBbjyzNXPD4Nbnzfn1N7pzHl6bPuC+SPXn0S9Xhpv7fmeH33rOoKRPHOSw6UQpRL6e93cekz3mb+/0kBxc1N7FRWxDGeI5pmkeYxeIJ2YGBj1pDQ2fnh4fPzefzF/jXcPXvFg0MDHx0aGjoREmSjly2bNmcut+ajlr4vYgaQ2jAd93+D/A8P29gYOADQ0NDJ4+MjJxRKpUWuYfaBfl8/oLBwcHz3fV3uVzuLMuyTi2VSsePjo7O88Uya0rpfSKXg47JHNteti4aPWztMjynfJN2eCmMF4zdaB5R7raO9K91N5pHrF1WWvBwtzV/tI2fV3bZQD2e9/fhy1mPSRaGt0H9iqfRqv9cnaXwfpVHIFCnvPy9iZZlzdXK5cNxqbTAHBs7wrKsI/1rbGzsiFKptKBcLh/up4DxW7Pvslfyb4FJ1pb/+qMuN9uTTz4517Ks+aVSacFYnVzGxsaOcGc+LhgdHZ3n56uq30fvM7kcPNQ2zERcaTprYl9W9fv8ZRX/e4TcMt2L1Wi9j1/AvaGl/t4D72y/1OCX2ftVVn73MDD1Pt+xXHxK630pl0OJWn/i3qyJiSB6oCEbaBP/69Gy131Sp+gD739rc6+oP7z2US5NvEO8Iwurif9v0dwr06MplyaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSaaaKKJJppoookmmmiiiSbeW/h/bt+uYrvOk4sAAAAASUVORK5CYII=',
                      u'name': u'MyPizza',
                      u'phone': False,
                      u'vat': False,
                      u'website': u'http://www.yourcompany.com'},
         u'currency': {u'decimals': 2,
                       u'id': 1,
                       u'name': u'EUR',
                       u'position': u'after',
                       u'rounding': 0.01,
                       u'symbol': u'\u20ac'},
         u'date': {u'date': 28,
                   u'day': 1,
                   u'hour': 15,
                   u'isostring': u'2015-12-28T14:29:57.461Z',
                   u'localestring': u'28/12/2015 15:29:57',
                   u'minute': 29,
                   u'month': 11,
                   u'year': 2015},
         u'footer': u'',
         u'header': u'',
         u'invoice_id': None,
         u'name': u'Ordine 00010-054-0009',
         u'orderlines': [{u'discount': 0,
                          u'price': 4,
                          u'price_display': 8,
                          u'price_with_tax': 8,
                          u'price_without_tax': 8,
                          u'product_description': False,
                          u'product_description_sale': False,
                          u'product_name': u'Birra',
                          u'quantity': 2,
                          u'tax': 0,
                          u'unit_name': u'Unit\xe0'}],
         u'paymentlines': [{u'amount': 58, u'journal': u'Cash (EUR)'}],
         u'precision': {u'money': 2, u'price': 2, u'quantity': 3},
         u'shop': {u'name': u'Stock'},
         u'subtotal': 8,
         u'tax_details': [],
         u'total_discount': 0,
         u'total_paid': 58,
         u'total_tax': 0,
         u'total_with_tax': 8,
         u'total_without_tax': 8}
        
        """
        
        txt = ''
        for line in receipt['orderlines']:
            txt += self._printRecItem(line)
        for line in receipt['paymentlines']:
            txt += self._printRecTotal(line)
        if receipt['total_discount']:
            txt += """<printRecMessage operator="1" message="Hai Risparmiato %s" messageType="2" index="2" font="4" />"""%str(receipt['total_discount']).replace('.',',')
        import pprint
        _logger.info(pprint.pformat(receipt))
        self.printerFiscalReceipt(txt) 
       
        


class EposPrint(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.queue = Queue()
        self.lock  = Lock()        
        self.status = {'status':'connecting', 'messages':[]}

    def push_task(self,task, data = None):
        self.lockedstart()
        self.queue.put((time.time(),task,data))
        
    def lockedstart(self):
        with self.lock:            
            if not self.isAlive():                
                self.daemon = True
                self.start()

    def set_status(self, status, message = None):
        if status == self.status['status']:
            if message != None and message != self.status['messages'][-1]:
                self.status['messages'].append(message)
        else:
            self.status['status'] = status
            if message:
                self.status['messages'] = [message]
            else:
                self.status['messages'] = []

        if status == 'error' and message:
            _logger.error('Epos Print Error: '+message)
        elif status == 'disconnected' and message:
            _logger.info('Disconnected Epos Print: %s', message)

    def get_status(self):
        self.lockedstart()
        return self.status                        

    def get_device(self):
        devobj = EpsonOBJ(IP)
        _logger.info(devobj.status())
        device_status = devobj.status()
        if device_status['@success'] == 'true':
            device_cpu = device_status['addInfo']['cpuRel']
            self.set_status('connected','Connected to cpuRel '+device_cpu+ ' IP '+IP )
        return devobj

    def run(self):
        """ 
        """
        device   = None

        while True: # barcodes loop
            if not device:
                time.sleep(5)   # wait until a suitable device is plugged
                printer = self.get_device()
                if not printer:
                    continue

            try:
                error = True
                timestamp, task, data = self.queue.get(True)
                if task == 'printXReport':
                    printer.printXReport()
                elif task == 'receipt': 
                    if timestamp >= time.time() - 1 * 60 * 60:
                        printer.print_receipt_body(data)
                        #printer.cut()
                elif task == 'xml_receipt':
                    if timestamp >= time.time() - 1 * 60 * 60:
                        printer.receipt(data)
                elif task == 'invoice':
                    if timestamp >= time.time() - 1 * 60 * 60:
                        printer.invoicet(data)                        
                elif task == 'cashbox':
                    if timestamp >= time.time() - 12:
                        self.open_cashbox(printer)
                elif task == 'printstatus':
                    printer.print_status(printer)
                elif task == 'status':
                    pass
                error = False

            except Exception as e:
                self.set_status('error',str(e))

eposprint_thread = EposPrint()
hw_proxy.drivers['eposprint'] = eposprint_thread        

eposprint_thread.push_task('printstatus')

class EposPrintDriver(hw_proxy.Proxy):
            
    @http.route('/hw_proxy/print_receipt', type='json', auth='none', cors='*')
    def print_receipt(self, receipt):
        _logger.info('Epson Print: PRINT RECEIPT') 
        eposprint_thread.push_task('receipt',receipt)

    @http.route('/hw_proxy/print_xml_receipt', type='json', auth='none', cors='*')
    def print_xml_receipt(self, receipt):
        _logger.info('Epson Print: PRINT XML RECEIPT') 
        eposprint_thread.push_task('xml_receipt',receipt)        

    @http.route('/hw_proxy/print_pdf_invoice', type='json', auth='none', cors='*')
    def print_pdf_invoice(self, pdfinvoice):
        eposprint_thread.push_task('invoice',pdfinvoice)        
