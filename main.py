import os
import json
import time
import random
import asyncio
import threading
from flask import Flask, render_template_string, Response
from flask_socketio import SocketIO
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent, LikeEvent, JoinEvent, ShareEvent, RoomUserSeqEvent

# ==========================================
# KONFIGURASI APLIKASI & GAME
# ==========================================
TIKTOK_USERNAME = "c_poek"
app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# Database Kata Sederhana untuk Game
KATA_DB = ["TERMUX", "PYTHON", "PROGRAMMER", "TIKTOK", "SERVER", "CODING", "DATABASE", "INTERNET", "KOMPUTER", "JARINGAN"]

# State Global
game_state = {
    "current_word": "",
    "scrambled_word": "",
    "status": "Menunggu Live Stream...",
    "viewers": 0,
    "likes": 0,
    "joins": 0,
    "shares": 0,
    "comments_count": 0,
    "leaderboard": {} # format: {"username": score}
}

def acak_kata():
    kata = random.choice(KATA_DB)
    game_state["current_word"] = kata
    l = list(kata)
    random.shuffle(l)
    game_state["scrambled_word"] = "".join(l)
    socketio.emit('game_update', {"scrambled": game_state["scrambled_word"]})

# Inisialisasi kata pertama
acak_kata()

# ==========================================
# ASSET FRONT-END (HTML, CSS, JS, PWA)
# ==========================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Tebak Kata - TikTok Live</title>
    <link rel="manifest" href="/manifest.json">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            background: #0f0f1a; 
            color: #ffffff; 
            font-family: 'Inter', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            width: 100vw;
            overflow: hidden;
        }
        /* Memaksa Rasio 4:3 Landscape */
        .app-container {
            width: 100vw;
            height: 75vw; /* 4:3 aspect ratio based on width */
            max-height: 100vh;
            max-width: 133.33vh; /* 4:3 aspect ratio based on height */
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            box-shadow: 0 0 30px rgba(0,0,0,0.8);
            position: relative;
            display: flex;
            flex-direction: row;
        }
        .left-panel {
            flex: 2;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            border-right: 2px solid rgba(255,255,255,0.1);
            padding: 2rem;
            position: relative;
        }
        .right-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 1rem;
            background: rgba(0,0,0,0.3);
        }
        .status-badge {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(255, 255, 255, 0.1);
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: bold;
        }
        .status-badge i { margin-right: 8px; color: #e74c3c; }
        
        /* Game UI */
        .title { font-size: 2rem; font-weight: 900; color: #00d2ff; text-transform: uppercase; margin-bottom: 10px; text-align: center; }
        .scrambled-box {
            font-size: 4rem;
            font-weight: 900;
            letter-spacing: 10px;
            background: -webkit-linear-gradient(#fff, #aaa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 20px 0;
        }
        .instruction { font-size: 1.2rem; color: #aaa; text-align: center; }
        
        /* Stats & Leaderboard UI */
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.05);
            padding: 10px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-card i { font-size: 1.5rem; margin-bottom: 5px; color: #00d2ff; }
        .stat-value { font-size: 1.2rem; font-weight: bold; }
        .stat-label { font-size: 0.8rem; color: #888; text-transform: uppercase; }
        
        .leaderboard-title {
            font-size: 1.2rem;
            font-weight: bold;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 10px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .leaderboard-title i { color: #f1c40f; }
        .lb-item {
            display: flex;
            justify-content: space-between;
            background: rgba(255,255,255,0.05);
            margin-bottom: 8px;
            padding: 10px;
            border-radius: 8px;
            align-items: center;
        }
        .lb-user {
            font-weight: bold;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 150px;
        }
        .lb-score { font-weight: 900; color: #2ecc71; }
        
        /* Notifications */
        .toast-container { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); width: 80%; pointer-events: none; }
        .toast {
            background: rgba(46, 204, 113, 0.9);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
            margin-top: 10px;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .toast.show { opacity: 1; }
    </style>
</head>
<body>

<div class="app-container" id="app">
    <div class="left-panel">
        <div class="status-badge" id="status-badge">
            <i class="fa-solid fa-circle-play"></i> <span id="status-text">Standby...</span>
        </div>
        
        <div class="title"><i class="fa-solid fa-gamepad"></i> Tebak Kata Unlimited</div>
        <div class="scrambled-box" id="scrambled-word">MEMUAT...</div>
        <div class="instruction">Jawab di komentar untuk menebak kata di atas!</div>
        
        <div class="toast-container" id="toast-container"></div>
    </div>
    
    <div class="right-panel">
        <div class="stats-grid">
            <div class="stat-card">
                <i class="fa-solid fa-eye"></i>
                <div class="stat-value" id="stat-viewers">0</div>
                <div class="stat-label">Penonton</div>
            </div>
            <div class="stat-card">
                <i class="fa-solid fa-heart"></i>
                <div class="stat-value" id="stat-likes">0</div>
                <div class="stat-label">Likes</div>
            </div>
            <div class="stat-card">
                <i class="fa-solid fa-comments"></i>
                <div class="stat-value" id="stat-comments">0</div>
                <div class="stat-label">Komentar</div>
            </div>
            <div class="stat-card">
                <i class="fa-solid fa-share-nodes"></i>
                <div class="stat-value" id="stat-shares">0</div>
                <div class="stat-label">Shares</div>
            </div>
        </div>
        
        <div class="leaderboard-title">
            <i class="fa-solid fa-trophy"></i> Top User
        </div>
        <div id="leaderboard-container">
            </div>
    </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
    // PWA Service Worker Registration
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').then(function(registration) {
            console.log('ServiceWorker registered with scope:', registration.scope);
        }).catch(function(err) {
            console.log('ServiceWorker registration failed:', err);
        });
    }

    const socket = io();

    // Elements
    const elScrambled = document.getElementById('scrambled-word');
    const elStatus = document.getElementById('status-text');
    const elStatusBadge = document.getElementById('status-badge');
    const elViewers = document.getElementById('stat-viewers');
    const elLikes = document.getElementById('stat-likes');
    const elComments = document.getElementById('stat-comments');
    const elShares = document.getElementById('stat-shares');
    const elLeaderboard = document.getElementById('leaderboard-container');
    const toastContainer = document.getElementById('toast-container');

    function showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'toast show';
        toast.innerHTML = `<i class="fa-solid fa-check-circle"></i> ${message}`;
        toastContainer.appendChild(toast);
        setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, 3000);
    }

    socket.on('connect', () => { console.log('Connected to server'); });

    socket.on('state_sync', (data) => {
        elScrambled.innerText = data.scrambled_word;
        elStatus.innerText = data.status;
        elViewers.innerText = data.viewers;
        elLikes.innerText = data.likes;
        elComments.innerText = data.comments_count;
        elShares.innerText = data.shares;
        updateLeaderboard(data.leaderboard);
        if(data.status === "Live Connected") elStatusBadge.style.color = "#2ecc71";
    });

    socket.on('game_update', (data) => {
        elScrambled.innerText = data.scrambled;
    });

    socket.on('status_update', (data) => {
        elStatus.innerText = data.msg;
    });

    socket.on('stats_update', (data) => {
        if (data.viewers !== undefined) elViewers.innerText = data.viewers;
        if (data.likes !== undefined) elLikes.innerText = data.likes;
        if (data.comments_count !== undefined) elComments.innerText = data.comments_count;
        if (data.shares !== undefined) elShares.innerText = data.shares;
    });

    socket.on('leaderboard_update', (data) => {
        updateLeaderboard(data.leaderboard);
    });

    socket.on('correct_answer', (data) => {
        showToast(`${data.username} menjawab benar! (+10 Poin)`);
    });

    function updateLeaderboard(lbData) {
        elLeaderboard.innerHTML = '';
        // Sort and get Top 3
        const sorted = Object.entries(lbData).sort((a, b) => b[1] - a[1]).slice(0, 3);
        if (sorted.length === 0) {
            elLeaderboard.innerHTML = '<div class="instruction" style="font-size: 0.9rem;">Belum ada skor</div>';
            return;
        }
        sorted.forEach(([user, score], index) => {
            let icon = index === 0 ? '<i class="fa-solid fa-medal" style="color: gold;"></i>' : 
                       index === 1 ? '<i class="fa-solid fa-medal" style="color: silver;"></i>' : 
                       '<i class="fa-solid fa-medal" style="color: #cd7f32;"></i>';
            elLeaderboard.innerHTML += `
                <div class="lb-item">
                    <span class="lb-user">${icon} ${user}</span>
                    <span class="lb-score">${score} Pts</span>
                </div>
            `;
        });
    }
</script>
</body>
</html>
"""

MANIFEST_JSON = """
{
  "name": "Tebak Kata Unlimited",
  "short_name": "TebakKata",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f0f1a",
  "theme_color": "#1a1a2e",
  "orientation": "landscape",
  "icons": [
    {
      "src": "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/svgs/solid/gamepad.svg",
      "sizes": "192x192",
      "type": "image/svg+xml"
    }
  ]
}
"""

SERVICE_WORKER_JS = """
self.addEventListener('install', function(event) {
    self.skipWaiting();
});
self.addEventListener('fetch', function(event) {
    // Basic passthrough SW
});
"""

# ==========================================
# FLASK ROUTES
# ==========================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/manifest.json')
def manifest():
    return Response(MANIFEST_JSON, mimetype='application/json')

@app.route('/sw.js')
def service_worker():
    return Response(SERVICE_WORKER_JS, mimetype='application/javascript')

@socketio.on('connect')
def handle_connect():
    socketio.emit('state_sync', game_state)

# ==========================================
# TIKTOK LIVE CLIENT & STANDBY SYSTEM
# ==========================================

def update_leaderboard(username, points=10):
    if username not in game_state["leaderboard"]:
        game_state["leaderboard"][username] = 0
    game_state["leaderboard"][username] += points
    socketio.emit('leaderboard_update', {"leaderboard": game_state["leaderboard"]})

def start_tiktok_client():
    client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)

    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        game_state["status"] = f"Live Connected (@{TIKTOK_USERNAME})"
        socketio.emit('status_update', {"msg": game_state["status"]})

    @client.on(DisconnectEvent)
    async def on_disconnect(event: DisconnectEvent):
        game_state["status"] = "Terputus. Mencoba reconnect..."
        socketio.emit('status_update', {"msg": game_state["status"]})

    @client.on(RoomUserSeqEvent)
    async def on_viewer(event: RoomUserSeqEvent):
        game_state["viewers"] = event.viewer_count
        socketio.emit('stats_update', {"viewers": game_state["viewers"]})

    @client.on(JoinEvent)
    async def on_join(event: JoinEvent):
        game_state["joins"] += 1

    @client.on(LikeEvent)
    async def on_like(event: LikeEvent):
        game_state["likes"] += event.like_count
        socketio.emit('stats_update', {"likes": game_state["likes"]})

    @client.on(ShareEvent)
    async def on_share(event: ShareEvent):
        game_state["shares"] += 1
        socketio.emit('stats_update', {"shares": game_state["shares"]})

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        game_state["comments_count"] += 1
        socketio.emit('stats_update', {"comments_count": game_state["comments_count"]})
        
        # Logika Game: Cek Jawaban
        komentar = event.comment.strip().upper()
        if komentar == game_state["current_word"]:
            username = event.user.nickname
            update_leaderboard(username)
            socketio.emit('correct_answer', {"username": username})
            acak_kata() # Lanjut ke kata berikutnya tanpa batas (Unlimited)

    # Sistem Standby (Auto-Retry jika offline)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            game_state["status"] = f"Mencari Live @{TIKTOK_USERNAME}..."
            socketio.emit('status_update', {"msg": game_state["status"]})
            client.run()
        except Exception as e:
            game_state["status"] = "Live Offline. Standby..."
            socketio.emit('status_update', {"msg": game_state["status"]})
            time.sleep(10) # Tunggu 10 detik sebelum mencoba reconnect otomatis

if __name__ == '__main__':
    # Jalankan TikTok Client di Background Thread
    threading.Thread(target=start_tiktok_client, daemon=True).start()
    
    # Jalankan Web Server
    print("Server berjalan di http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)

