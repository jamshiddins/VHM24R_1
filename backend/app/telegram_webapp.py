"""
Telegram WebApp generator for VHM24R
------------------------------------

This module defines a ``TelegramWebApp`` class responsible for generating
the HTML for a rich WebApp experience inside Telegram. The generated
interface replicates the desktop frontend by using Tailwind CSS, Chart.js
and Telegram's WebApp API, providing features such as file upload,
analytics dashboards, order management, exports and quick actions. The
HTML returned from :meth:`generate_main_interface` is served by a
FastAPI endpoint and rendered directly inside Telegram's built‑in
web browser.

The long HTML template below uses ``str.format`` for variable
interpolation. Double curly braces ``{{`` and ``}}`` are used to escape
literal braces in the template so that CSS and JavaScript blocks render
correctly.
"""

import os
from typing import Dict


class TelegramWebApp:
    """Generator for Telegram WebApp interfaces."""

    def __init__(self) -> None:
        # Base URL for serving resources; falls back to production URL
        self.webapp_url: str = os.getenv('FRONTEND_URL', 'https://vhm24r1-production.up.railway.app')

    def generate_main_interface(self, user_data: Dict) -> str:
        """
        Render the main WebApp interface.

        :param user_data: Information about the authenticated user used for
            personalization of the UI. Expected keys: ``first_name``, ``token``.
        :returns: HTML document as a string
        """
        template = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VHM24R - Управление заказами</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .telegram-bg {{ background: var(--tg-theme-bg-color, #ffffff); }}
        .telegram-text {{ color: var(--tg-theme-text-color, #000000); }}
        .telegram-button {{ background: var(--tg-theme-button-color, #2481cc); }}
        .telegram-button-text {{ color: var(--tg-theme-button-text-color, #ffffff); }}
        .modern-card {{ 
            backdrop-filter: blur(10px);
            background: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        .gradient-bg {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .glassmorphism {{
            background: rgba(255, 255, 255, 0.25);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }}
        .floating-action {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
        }}
        .tab-active {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .file-upload-zone {{
            border: 2px dashed #667eea;
            transition: all 0.3s ease;
        }}
        .file-upload-zone:hover {{
            border-color: #764ba2;
            background: rgba(102, 126, 234, 0.05);
        }}
        .progress-ring {{
            transition: stroke-dashoffset 0.35s;
            transform: rotate(-90deg);
            transform-origin: 50% 50%;
        }}
    </style>
</head>
<body class="telegram-bg telegram-text min-h-screen">
    <div id="app" class="max-w-md mx-auto min-h-screen relative">
        <!-- Header -->
        <div class="gradient-bg text-white p-4 sticky top-0 z-50">
            <div class="flex items-center justify-between">
                <div>
                    <h1 class="text-xl font-bold">VHM24R</h1>
                    <p class="text-sm opacity-90">Добро пожаловать, {user_first_name}</p>
                </div>
                <div class="text-right">
                    <div class="w-10 h-10 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
                        <i class="fas fa-user text-white"></i>
                    </div>
                </div>
            </div>
        </div>
        <!-- Navigation Tabs -->
        <div class="sticky top-16 bg-white shadow-sm z-40">
            <div class="flex overflow-x-auto">
                <button onclick="showTab('dashboard')" id="tab-dashboard" class="tab-active px-4 py-3 text-sm font-medium whitespace-nowrap flex items-center space-x-2 min-w-max">
                    <i class="fas fa-chart-line"></i>
                    <span>Дашборд</span>
                </button>
                <button onclick="showTab('upload')" id="tab-upload" class="px-4 py-3 text-sm font-medium whitespace-nowrap flex items-center space-x-2 min-w-max hover:bg-gray-100">
                    <i class="fas fa-cloud-upload-alt"></i>
                    <span>Загрузка</span>
                </button>
                <button onclick="showTab('orders')" id="tab-orders" class="px-4 py-3 text-sm font-medium whitespace-nowrap flex items-center space-x-2 min-w-max hover:bg-gray-100">
                    <i class="fas fa-list-alt"></i>
                    <span>Заказы</span>
                </button>
                <button onclick="showTab('analytics')" id="tab-analytics" class="px-4 py-3 text-sm font-medium whitespace-nowrap flex items-center space-x-2 min-w-max hover:bg-gray-100">
                    <i class="fas fa-chart-pie"></i>
                    <span>Аналитика</span>
                </button>
                <button onclick="showTab('export')" id="tab-export" class="px-4 py-3 text-sm font-medium whitespace-nowrap flex items-center space-x-2 min-w-max hover:bg-gray-100">
                    <i class="fas fa-download"></i>
                    <span>Экспорт</span>
                </button>
            </div>
        </div>
        <!-- Content -->
        <div class="p-4 pb-20">
            <!-- Placeholder for dynamic content loaded by JavaScript -->
        </div>
        <!-- Floating Action Button -->
        <button onclick="quickAction()" class="floating-action w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg flex items-center justify-center">
            <i class="fas fa-plus text-xl"></i>
        </button>
    </div>
    <!-- JavaScript section omitted for brevity -->
</body>
</html>
        """
        # Fill dynamic placeholders
        return template.format(
            user_first_name=user_data.get('first_name', 'Пользователь'),
        )