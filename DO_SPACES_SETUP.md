# 🔑 Получение Secret Key для DigitalOcean Spaces

## ℹ️ Текущие данные:

✅ **Access Key ID**: `DO00XEB6BC6XZ8Q2M4KQ`  
✅ **Access Key Name**: `vhm24report`  
✅ **Endpoint**: `https://vhm24r1-files.fra1.digitaloceanspaces.com`  
✅ **Bucket**: `vhm24r1-files`  
✅ **Region**: `fra1`  

❌ **Secret Key**: Нужно получить!

## 🔍 Как получить Secret Key:

### Вариант 1: Если ключ уже создан
1. Войдите в [DigitalOcean Console](https://cloud.digitalocean.com/)
2. Перейдите в **API** → **Spaces Keys**
3. Найдите ключ с именем `vhm24report`
4. Если Secret Key скрыт, нажмите **"Regenerate"** для создания нового

### Вариант 2: Создание нового ключа
1. Войдите в [DigitalOcean Console](https://cloud.digitalocean.com/)
2. Перейдите в **API** → **Spaces Keys**
3. Нажмите **"Generate New Key"**
4. Введите имя: `vhm24r-production`
5. Скопируйте **Access Key ID** и **Secret Key**

## ⚠️ Важно!

- Secret Key показывается только один раз при создании
- Обязательно сохраните его в безопасном месте
- Если потеряли Secret Key, нужно создать новый ключ

## 🔧 После получения Secret Key:

Обновите переменную в Railway:
```env
DO_SPACES_SECRET=ваш-полученный-secret-key
```

## 🧪 Проверка работы Spaces:

После деплоя проверьте загрузку файла через API:
```bash
curl -X POST "https://ваш-домен.railway.app/api/v1/upload" \
     -H "Authorization: Bearer ваш-токен" \
     -F "files=@test.csv"
```

## 📞 Поддержка:

Если возникли проблемы с DigitalOcean Spaces:
- [Документация DigitalOcean Spaces](https://docs.digitalocean.com/products/spaces/)
- [Поддержка DigitalOcean](https://www.digitalocean.com/support/)

---

**После получения Secret Key ваша система будет полностью готова к работе! 🚀**
