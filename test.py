from scapy.all import *

import math



def packet_entropy(pkt):

    if IP in pkt and pkt.haslayer(TCP):

        ip_payload = pkt[IP].payload

        if len(ip_payload) > 0:

            counts = dict()

            for byte in ip_payload:

                if byte in counts:

                    counts[byte] += 1

                else:

                    counts[byte] = 1

            entropy = 0

            for count in counts.values():

                probability = count / float(len(ip_payload))

                entropy -= probability * math.log(probability, 2)

            print("Entropy: {:.3f}".format(entropy))



sniff(filter="ip", prn=packet_entropy)


