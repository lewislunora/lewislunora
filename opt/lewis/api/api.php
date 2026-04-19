<?php
/**
 * 翔川 Lewis AI - 後端 API
 * MVVM 後端服務
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

// 處理 OPTIONS 請求
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// 簡單的資料存儲（實際應使用資料庫）
$dataFile = __DIR__ . '/data/';
if (!file_exists($dataFile)) {
    mkdir($dataFile, 0777, true);
}

// 獲取請求方法
$method = $_SERVER['REQUEST_METHOD'];
$request = $_GET['request'] ?? '';

// 模擬數據
$services = [
    ['id' => 1, 'name' => '八字命理分析', 'price' => 3000, 'icon' => '🪐', 'desc' => '完整命盤分析，八字五行解讀', 'active' => true],
    ['id' => 2, 'name' => '五行平衡諮詢', 'price' => 2500, 'icon' => '🌿', 'desc' => '五行屬性建議，調整運勢', 'active' => true],
    ['id' => 3, 'name' => '寶寶命名服務', 'price' => 5000, 'icon' => '✍️', 'desc' => '命理取名，音義兼備', 'active' => true],
    ['id' => 4, 'name' => '星座運勢分析', 'price' => 1000, 'icon' => '⭐', 'desc' => '月度星座運程解讀', 'active' => true],
    ['id' => 5, 'name' => '創業方向諮詢', 'price' => 5000, 'icon' => '🚀', 'desc' => '創業方向建議與規劃', 'active' => true],
    ['id' => 6, 'name' => 'AI Telegram Bot', 'price' => 15000, 'icon' => '🤖', 'desc' => '客製化 AI 機器人開發', 'active' => true],
    ['id' => 7, 'name' => 'DevOps 顧問', 'price' => 20000, 'icon' => '☁️', 'desc' => 'K8s 架構、雲端遷移', 'active' => true],
    ['id' => 8, 'name' => '技術諮詢', 'price' => 2000, 'icon' => '💻', 'desc' => '單次技術問題解答', 'active' => true],
];

$bookings = [
    ['id' => 1, 'service_id' => 1, 'service_name' => '八字命理分析', 'name' => '王小明', 'email' => 'wang@test.com', 'status' => 'completed', 'created_at' => '2026-04-01'],
    ['id' => 2, 'service_id' => 5, 'service_name' => '創業方向諮詢', 'name' => '李老闆', 'email' => 'li@company.com', 'status' => 'pending', 'created_at' => '2026-04-05'],
    ['id' => 3, 'service_id' => 6, 'service_name' => 'AI Telegram Bot', 'name' => '陳工程師', 'email' => 'chen@tech.com', 'status' => 'pending', 'created_at' => '2026-04-06'],
];

$users = [
    ['id' => 1, 'name' => 'Admin', 'email' => 'admin@lewis.ai', 'role' => 'admin', 'created_at' => '2026-01-01'],
    ['id' => 2, 'name' => '測試用戶', 'email' => 'test@lewis.ai', 'role' => 'user', 'created_at' => '2026-04-01'],
];

$stats = [
    'total_users' => count($users),
    'total_bookings' => count($bookings),
    'completed_orders' => count(array_filter($bookings, fn($b) => $b['status'] === 'completed')),
    'pending_orders' => count(array_filter($bookings, fn($b) => $b['status'] === 'pending')),
    'total_revenue' => array_sum(array_map(fn($b) => array_find($services, fn($s) => $s['id'] === $b['service_id'])['price'] ?? 0, $bookings)),
];

// 路由處理
switch ($request) {
    // 獲取服務列表
    case 'services':
        echo json_encode([
            'success' => true,
            'data' => array_values(array_filter($services, fn($s) => $s['active']))
        ]);
        break;
    
    // 獲取單一服務
    case 'service':
        $id = intval($_GET['id'] ?? 0);
        $service = array_find($services, fn($s) => $s['id'] === $id);
        echo json_encode([
            'success' => $service ? true : false,
            'data' => $service
        ]);
        break;
    
    // 獲取預約列表
    case 'bookings':
        echo json_encode([
            'success' => true,
            'data' => $bookings
        ]);
        break;
    
    // 新增預約
    case 'booking/create':
        $input = json_decode(file_get_contents('php://input'), true);
        if ($input) {
            $newBooking = [
                'id' => count($bookings) + 1,
                'service_id' => $input['service_id'] ?? 0,
                'service_name' => $input['service_name'] ?? '',
                'name' => $input['name'] ?? '',
                'email' => $input['email'] ?? '',
                'message' => $input['message'] ?? '',
                'status' => 'pending',
                'created_at' => date('Y-m-d')
            ];
            $bookings[] = $newBooking;
            echo json_encode(['success' => true, 'data' => $newBooking]);
        } else {
            echo json_encode(['success' => false, 'message' => 'Invalid input']);
        }
        break;
    
    // 更新預約狀態
    case 'booking/update':
        $input = json_decode(file_get_contents('php://input'), true);
        if ($input && isset($input['id'])) {
            foreach ($bookings as &$booking) {
                if ($booking['id'] === $input['id']) {
                    $booking['status'] = $input['status'] ?? $booking['status'];
                }
            }
            echo json_encode(['success' => true]);
        } else {
            echo json_encode(['success' => false]);
        }
        break;
    
    // 獲取統計
    case 'stats':
        echo json_encode([
            'success' => true,
            'data' => $stats
        ]);
        break;
    
    // 獲取用戶列表
    case 'users':
        echo json_encode([
            'success' => true,
            'data' => $users
        ]);
        break;
    
    // 用戶登入
    case 'login':
        $input = json_decode(file_get_contents('php://input'), true);
        if ($input) {
            $user = array_find($users, fn($u) => $u['email'] === $input['email']);
            if ($user) {
                echo json_encode(['success' => true, 'data' => $user, 'token' => bin2hex(random_bytes(32))]);
            } else {
                echo json_encode(['success' => false, 'message' => 'User not found']);
            }
        } else {
            echo json_encode(['success' => false, 'message' => 'Invalid input']);
        }
        break;
    
    // 用戶註冊
    case 'register':
        $input = json_decode(file_get_contents('php://input'), true);
        if ($input) {
            $newUser = [
                'id' => count($users) + 1,
                'name' => $input['name'] ?? '',
                'email' => $input['email'] ?? '',
                'role' => 'user',
                'created_at' => date('Y-m-d')
            ];
            $users[] = $newUser;
            echo json_encode(['success' => true, 'data' => $newUser]);
        } else {
            echo json_encode(['success' => false]);
        }
        break;
    
    // 預設返回
    default:
        echo json_encode([
            'success' => true,
            'message' => '翔川 Lewis API 服務中',
            'version' => '1.0.0',
            'endpoints' => [
                'GET /api?request=services',
                'GET /api?request=service&id=1',
                'GET /api?request=bookings',
                'POST /api?request=booking/create',
                'GET /api?request=stats',
                'GET /api?request=users',
                'POST /api?request=login',
                'POST /api?request=register'
            ]
        ]);
        break;
}

// 輔助函數
function array_find($array, $callback) {
    foreach ($array as $item) {
        if ($callback($item)) return $item;
    }
    return null;
}