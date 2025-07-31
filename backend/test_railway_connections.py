"""
Скрипт для проверки подключений к PostgreSQL и Redis на Railway
"""
import os
import asyncio
import traceback
from datetime import datetime
from typing import Dict, Any

# Загружаем переменные окружения из .env файла
from dotenv import load_dotenv
load_dotenv()

# Подключения
import redis
import redis.asyncio as async_redis
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Настройка логирования
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RailwayConnectionTester:
    """Тестер подключений к Railway сервисам"""
    
    def __init__(self):
        self.results = {
            'postgresql': {'status': 'not_tested', 'details': {}},
            'redis': {'status': 'not_tested', 'details': {}},
            'jwt_service': {'status': 'not_tested', 'details': {}},
            'cache_service': {'status': 'not_tested', 'details': {}}
        }
        
        # Получаем переменные окружения
        self.database_url = os.getenv('DATABASE_URL')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY')
        
        logger.info("=== ПРОВЕРКА КОНФИГУРАЦИИ RAILWAY ===")
        logger.info(f"DATABASE_URL: {'✓ установлена' if self.database_url else '✗ не установлена'}")
        logger.info(f"REDIS_URL: {self.redis_url}")
        logger.info(f"JWT_SECRET_KEY: {'✓ установлена' if self.jwt_secret else '✗ не установлена'}")
        print()

    def test_postgresql_connection(self) -> Dict[str, Any]:
        """Тестирование PostgreSQL подключения"""
        logger.info("🔍 Тестирование PostgreSQL подключения...")
        
        if not self.database_url:
            return {
                'status': 'failed',
                'error': 'DATABASE_URL не установлена',
                'recommendation': 'Установите переменную DATABASE_URL от Railway PostgreSQL сервиса'
            }
        
        if self.database_url.startswith('sqlite'):
            return {
                'status': 'warning',
                'error': 'Используется SQLite вместо PostgreSQL',
                'current_db': self.database_url,
                'recommendation': 'Замените DATABASE_URL на PostgreSQL URL от Railway'
            }
        
        try:
            # Тест с psycopg2
            logger.info("  📋 Тестирование прямого подключения...")
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version_result = cursor.fetchone()
            version = version_result[0] if version_result else "Unknown"
            cursor.close()
            conn.close()
            
            # Тест с SQLAlchemy
            logger.info("  📋 Тестирование SQLAlchemy...")
            engine = create_engine(self.database_url)
            SessionLocal = sessionmaker(bind=engine)
            
            with SessionLocal() as session:
                result = session.execute(text("SELECT current_database(), current_user;"))
                db_info = result.fetchone()
                database_name = db_info[0] if db_info else "Unknown"
                user_name = db_info[1] if db_info else "Unknown"
            
            # Проверяем таблицы
            logger.info("  📋 Проверка существующих таблиц...")
            with SessionLocal() as session:
                tables_result = session.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """))
                tables = [row[0] for row in tables_result.fetchall()]
            
            return {
                'status': 'success',
                'version': version,
                'database': database_name,
                'user': user_name,
                'tables': tables,
                'tables_count': len(tables),
                'connection_test': 'successful'
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc(),
                'recommendation': 'Проверьте правильность DATABASE_URL и доступность PostgreSQL на Railway'
            }

    def test_redis_connection(self) -> Dict[str, Any]:
        """Тестирование Redis подключения"""
        logger.info("🔍 Тестирование Redis подключения...")
        
        try:
            # Тест синхронного Redis
            logger.info("  📋 Тестирование синхронного Redis...")
            sync_client = redis.from_url(self.redis_url, decode_responses=True)
            
            if sync_client is None:
                raise Exception("Не удалось создать Redis клиент")
            
            sync_client.ping()
            
            # Тест записи/чтения
            test_key = f"railway_test_{datetime.now().timestamp()}"
            sync_client.set(test_key, "test_value", ex=60)
            retrieved_value = sync_client.get(test_key)
            sync_client.delete(test_key)
            
            # Получаем информацию о Redis
            info = sync_client.info()
            memory_info = sync_client.info('memory')
            
            sync_client.close()
            
            return {
                'status': 'success',
                'redis_version': info.get('redis_version'),
                'connected_clients': info.get('connected_clients'),
                'used_memory_human': memory_info.get('used_memory_human'),
                'keyspace': info.get('db0', {}),
                'test_write_read': 'successful' if retrieved_value == "test_value" else 'failed',
                'connection_test': 'successful'
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc(),
                'recommendation': 'Проверьте REDIS_URL и доступность Redis на Railway'
            }

    async def test_async_redis_connection(self) -> Dict[str, Any]:
        """Тестирование асинхронного Redis подключения"""
        logger.info("🔍 Тестирование асинхронного Redis подключения...")
        
        try:
            # Асинхронный Redis клиент
            logger.info("  📋 Тестирование асинхронного Redis...")
            async_client = async_redis.from_url(
                self.redis_url, 
                encoding="utf-8", 
                decode_responses=True
            )
            
            await async_client.ping()
            
            # Тест записи/чтения
            test_key = f"async_railway_test_{datetime.now().timestamp()}"
            await async_client.set(test_key, "async_test_value", ex=60)
            retrieved_value = await async_client.get(test_key)
            await async_client.delete(test_key)
            
            # Получаем информацию
            info = await async_client.info()
            await async_client.close()
            
            return {
                'status': 'success',
                'async_test': 'successful',
                'test_write_read': 'successful' if retrieved_value == "async_test_value" else 'failed',
                'server_info': {
                    'version': info.get('redis_version'),
                    'uptime': info.get('uptime_in_seconds')
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def test_jwt_service_integration(self) -> Dict[str, Any]:
        """Тестирование интеграции JWT сервиса с Redis"""
        logger.info("🔍 Тестирование JWT сервиса...")
        
        try:
            # Импортируем JWT сервис
            from app.services.secure_jwt_service import secure_jwt_service, TokenType
            
            # Проверяем подключение к Redis в JWT сервисе
            jwt_redis_status = {
                'redis_client_exists': 'true' if secure_jwt_service.redis_client is not None else 'false',
                'blacklist_service_exists': 'true' if secure_jwt_service.blacklist is not None else 'false',
            }
            
            # Проверяем создание токена
            if self.jwt_secret:
                try:
                    test_token = secure_jwt_service.create_token(
                        user_id=999,
                        username="test_user",
                        roles=["user"],
                        permissions=["read"],
                        token_type=TokenType.ACCESS
                    )
                    
                    # Проверяем верификацию
                    payload = secure_jwt_service.verify_token(test_token, TokenType.ACCESS)
                    
                    jwt_redis_status.update({
                        'token_creation': 'successful',
                        'token_verification': 'successful',
                        'user_id_match': 'successful' if str(payload.get('sub')) == '999' else 'failed'
                    })
                    
                except Exception as token_error:
                    jwt_redis_status.update({
                        'token_creation': 'failed',
                        'token_error': str(token_error)
                    })
            
            # Проверяем blacklist функциональность
            try:
                test_jti = "test_jti_123"
                secure_jwt_service.blacklist.add_token(test_jti, 9999999999, "test")
                is_blacklisted = secure_jwt_service.blacklist.is_blacklisted(test_jti)
                blacklist_info = secure_jwt_service.blacklist.get_blacklist_info(test_jti)
                
                jwt_redis_status.update({
                    'blacklist_add': 'successful',
                    'blacklist_check': 'successful' if is_blacklisted else 'failed',
                    'blacklist_info': 'successful' if blacklist_info else 'failed'
                })
                
            except Exception as blacklist_error:
                jwt_redis_status.update({
                    'blacklist_error': str(blacklist_error)
                })
            
            return {
                'status': 'success' if jwt_redis_status.get('redis_client_exists') else 'warning',
                **jwt_redis_status
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    async def test_cache_service_integration(self) -> Dict[str, Any]:
        """Тестирование интеграции кэш сервиса"""
        logger.info("🔍 Тестирование кэш сервиса...")
        
        try:
            from app.services.cache_service import cache_service
            
            # Подключаемся к кэшу
            await cache_service.connect()
            
            # Проверяем статус подключения
            cache_status = {
                'redis_connected': 'true' if cache_service.connected else 'false',
                'redis_client_exists': 'true' if cache_service.redis_client is not None else 'false',
                'memory_cache_exists': 'true' if cache_service.memory_cache is not None else 'false'
            }
            
            # Тестируем операции кэша
            test_key = f"cache_test_{datetime.now().timestamp()}"
            test_value = {"test": "data", "timestamp": datetime.now().isoformat()}
            
            # Тест записи и чтения
            await cache_service.set(test_key, test_value, expire=300)
            retrieved_value = await cache_service.get(test_key)
            
            cache_status.update({
                'write_test': 'successful',
                'read_test': 'successful' if retrieved_value == test_value else 'failed',
                'retrieved_data_match': 'successful' if retrieved_value == test_value else 'failed'
            })
            
            # Тест удаления
            await cache_service.delete(test_key)
            deleted_check = await cache_service.get(test_key)
            
            cache_status.update({
                'delete_test': 'successful' if deleted_check is None else 'failed'
            })
            
            # Получаем статистику
            stats = await cache_service.get_stats()
            health = await cache_service.health_check()
            
            # Преобразуем статистику в строковое представление
            stats_str = str(stats) if stats else 'unavailable'
            health_str = str(health) if health else 'unavailable'
            
            cache_status.update({
                'statistics': stats_str,
                'health_check': health_str
            })
            
            await cache_service.disconnect()
            
            return {
                'status': 'success',
                **cache_status
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    async def run_all_tests(self) -> Dict[str, Any]:
        """Запуск всех тестов"""
        logger.info("🚀 Запуск комплексного тестирования Railway подключений...")
        print()
        
        # PostgreSQL тест
        self.results['postgresql'] = self.test_postgresql_connection()
        logger.info(f"PostgreSQL: {self.results['postgresql']['status']}")
        
        # Redis синхронный тест
        self.results['redis'] = self.test_redis_connection()
        logger.info(f"Redis (sync): {self.results['redis']['status']}")
        
        # Redis асинхронный тест
        async_redis_result = await self.test_async_redis_connection()
        self.results['redis']['async_test'] = async_redis_result
        logger.info(f"Redis (async): {async_redis_result['status']}")
        
        # JWT сервис тест
        self.results['jwt_service'] = self.test_jwt_service_integration()
        logger.info(f"JWT Service: {self.results['jwt_service']['status']}")
        
        # Cache сервис тест
        self.results['cache_service'] = await self.test_cache_service_integration()
        logger.info(f"Cache Service: {self.results['cache_service']['status']}")
        
        return self.results

    def print_detailed_report(self):
        """Печать детального отчета"""
        print("\n" + "="*80)
        print("🔍 ДЕТАЛЬНЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ RAILWAY ПОДКЛЮЧЕНИЙ")
        print("="*80)
        
        for service, result in self.results.items():
            print(f"\n📊 {service.upper()}")
            print("-" * 50)
            
            status = result.get('status', 'unknown')
            status_icon = {
                'success': '✅',
                'warning': '⚠️', 
                'failed': '❌',
                'not_tested': '⏸️'
            }.get(status, '❓')
            
            print(f"Статус: {status_icon} {status}")
            
            if status == 'success':
                if service == 'postgresql':
                    print(f"  База данных: {result.get('database', 'N/A')}")
                    print(f"  Пользователь: {result.get('user', 'N/A')}")
                    print(f"  Таблиц: {result.get('tables_count', 0)}")
                    if result.get('tables'):
                        print(f"  Существующие таблицы: {', '.join(result['tables'][:5])}")
                
                elif service == 'redis':
                    print(f"  Версия Redis: {result.get('redis_version', 'N/A')}")
                    print(f"  Память: {result.get('used_memory_human', 'N/A')}")
                    print(f"  Клиенты: {result.get('connected_clients', 'N/A')}")
                
                elif service == 'jwt_service':
                    print(f"  Redis клиент: {'✅' if result.get('redis_client_exists') else '❌'}")
                    print(f"  Создание токенов: {result.get('token_creation', 'N/A')}")
                    print(f"  Blacklist: {result.get('blacklist_check', 'N/A')}")
                
                elif service == 'cache_service':
                    print(f"  Redis подключен: {'✅' if result.get('redis_connected') else '❌'}")
                    stats = result.get('statistics', {})
                    if stats:
                        print(f"  Hit rate: {stats.get('hit_rate_percent', 0)}%")
                        print(f"  Операций: {stats.get('total_operations', 0)}")
            
            elif status in ['failed', 'warning']:
                error = result.get('error', 'Неизвестная ошибка')
                print(f"  ❌ Ошибка: {error}")
                
                recommendation = result.get('recommendation')
                if recommendation:
                    print(f"  💡 Рекомендация: {recommendation}")
        
        print("\n" + "="*80)
        self.print_recommendations()

    def print_recommendations(self):
        """Печать рекомендаций"""
        print("💡 РЕКОМЕНДАЦИИ ДЛЯ НАСТРОЙКИ RAILWAY")
        print("="*80)
        
        recommendations = []
        
        # PostgreSQL рекомендации
        if self.results['postgresql']['status'] != 'success':
            if not self.database_url:
                recommendations.append(
                    "🔧 Установите DATABASE_URL от Railway PostgreSQL сервиса:\n"
                    "   railway variables set DATABASE_URL=postgresql://user:pass@host:port/db"
                )
            elif self.database_url.startswith('sqlite'):
                recommendations.append(
                    "🔧 Замените SQLite на PostgreSQL от Railway:\n"
                    "   Получите DATABASE_URL из Railway Dashboard → PostgreSQL сервиса"
                )
        
        # Redis рекомендации
        if self.results['redis']['status'] != 'success':
            recommendations.append(
                "🔧 Настройте Redis на Railway:\n"
                "   1. Добавьте Redis сервис в Railway\n"
                "   2. Установите REDIS_URL: railway variables set REDIS_URL=redis://..."
            )
        
        # JWT рекомендации
        if not self.jwt_secret:
            recommendations.append(
                "🔧 Установите JWT_SECRET_KEY:\n"
                "   railway variables set JWT_SECRET_KEY='your-very-secure-secret-key-32+chars'"
            )
        
        # Общие рекомендации
        if self.results['postgresql']['status'] == 'success' and self.results['redis']['status'] == 'success':
            recommendations.append(
                "✅ Подключения работают! Рекомендуем:\n"
                "   - Настроить мониторинг подключений\n"
                "   - Настроить резервное копирование PostgreSQL\n"
                "   - Оптимизировать настройки кэширования Redis"
            )
        
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec}")

async def main():
    """Главная функция тестирования"""
    tester = RailwayConnectionTester()
    
    # Запускаем все тесты
    results = await tester.run_all_tests()
    
    # Выводим детальный отчет
    tester.print_detailed_report()
    
    # Возвращаем общий статус
    overall_status = 'success'
    for service, result in results.items():
        if result['status'] == 'failed':
            overall_status = 'failed'
            break
        elif result['status'] == 'warning' and overall_status == 'success':
            overall_status = 'warning'
    
    print(f"\n🎯 ОБЩИЙ СТАТУС: {overall_status.upper()}")
    
    return results, overall_status

if __name__ == "__main__":
    asyncio.run(main())
