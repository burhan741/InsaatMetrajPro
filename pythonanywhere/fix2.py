c = open('/home/burhan852/app.py').read()

# Baslik degistir - tarayicinin yeni HTML yukleyip yuklemedigini test et
c = c.replace('<title>Santiye Puantaj</title>', '<title>SP v4</title>')
c = c.replace('<title>Şantiye Puantaj</title>', '<title>SP v4</title>')

# Sayfa acilir acilmaz pList'i guncelle - JS calisiyor mu test et
c = c.replace(
    "document.getElementById('pList').innerHTML = '<div class=\"empty\" style=\"color:#a0a0a0;\">⏳ API bağlanıyor...</div>';",
    "document.getElementById('pList').innerHTML = 'JS CALISIYOR - API bekleniyor';"
)

# window.onerror ekle - JS hatasini ekranda goster
old_script = '<script>'
new_script = '''<script>
window.onerror = function(msg, src, line) {
    document.getElementById('pList').innerHTML = 'HATA: ' + msg + ' (satir:' + line + ')';
    return true;
};'''
c = c.replace(old_script, new_script, 1)

with open('/home/burhan852/app.py', 'w') as f:
    f.write(c)
print('Tamam!')
