c = open('/home/burhan852/app.py').read()
c = c.replace('p?.calisma_durumu', '(p&&p.calisma_durumu)')
c = c.replace('p?.giris_saati', '(p&&p.giris_saati)')
c = c.replace('p?.cikis_saati', '(p&&p.cikis_saati)')
c = c.replace('p?.mesai_saat', '(p&&p.mesai_saat)')
c = c.replace('p?.yapilan_is', '(p&&p.yapilan_is)')
with open('/home/burhan852/app.py', 'w') as f:
    f.write(c)
print('Tamam! Kalan ?.:', c.count('?.'))
