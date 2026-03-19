import os
import random
import asyncio
import threading
import time
from flask import Flask, render_template_string, Response
from flask_socketio import SocketIO
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent, LikeEvent, JoinEvent, ShareEvent, RoomUserSeqEvent

# ==========================================
# KONFIGURASI APLIKASI
# ==========================================
TIKTOK_USERNAME = "gamemodapkofficial"
app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

# Database Kata - Bisa lo tambahin sesuka hati
KATA_DB = ["TERMUX", "PYTHON", "KODING", "TIKTOK", "SERVER", "DATABASE", "INTERNET", "KOMPUTER", "LINUX", "GITHUB", "API", "MOBILE", "GAMER", "DATA", "LOGIKA", "SCRIPT"]

game_state = {
    "current_word": "",
    "scrambled_word": "",
    "status": "Standby Mode...",
    "viewers": 0,
    "likes": 0,
    "comments_count": 0,
    "shares": 0,
    "leaderboard": {}
}

def acak_kata():
    """Fungsi Inti: Mengacak kata baru secara tak terbatas"""
    kata_baru = random.choice(KATA_DB)
    game_state["current_word"] = kata_baru
    l = list(kata_baru)
    random.shuffle(l)
    game_state["scrambled_word"] = "".join(l)
    # Broadcast ke semua tab browser yang buka
    socketio.emit('game_update', {"scrambled": game_state["scrambled_word"]})

# Generate kata pertama saat start
acak_kata()

# ==========================================
# UI FRONT-END (PURE BLACK & RESPONSIVE 4:3)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#000000">
    <title>Tebak Kata Unlimited</title>
    <link rel="manifest" href="/manifest.json">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            background: #000000; 
            color: #ffffff; 
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            display: flex; justify-content: center; align-items: center;
            height: 100vh; width: 100vw; overflow: hidden;
        }

        /* Container 4:3 - Anti Terpotong */
        .app-container {
            position: relative;
            height: 95vh;
            aspect-ratio: 4 / 3;
            background: #000000;
            display: flex;
            border: 2px solid #1a1a1a;
            box-shadow: 0 0 50px rgba(0,210,255,0.1);
        }

        #start-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: #000; z-index: 9999;
            display: flex; flex-direction: column; justify-content: center; align-items: center;
            cursor: pointer; text-align: center;
        }

        /* Panel Kiri (Game) */
        .left-panel {
            flex: 2.5;
            display: flex; flex-direction: column;
            justify-content: center; align-items: center;
            padding: 20px; position: relative;
            border-right: 1px solid #1a1a1a;
        }

        /* Panel Kanan (Stats) */
        .right-panel {
            flex: 1;
            background: #050505;
            display: flex; flex-direction: column;
            padding: 20px 15px;
        }

        .status-badge {
            position: absolute; top: 20px; left: 20px;
            background: #111; padding: 6px 15px; border-radius: 20px;
            font-size: 12px; border: 1px solid #222;
        }

        .scrambled-box {
            font-size: clamp(3rem, 8vw, 6rem); /* Ukuran font adaptif */
            font-weight: 900; letter-spacing: 12px;
            color: #ffffff; margin: 20px 0;
            text-shadow: 0 0 30px rgba(255,255,255,0.2);
            text-transform: uppercase;
        }

        .title-game { font-size: 1.8rem; color: #00d2ff; font-weight: 800; letter-spacing: 2px; }

        .stats-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
            margin-bottom: 25px;
        }
        .stat-card {
            background: #0f0f0f; padding: 12px;
            border-radius: 12px; text-align: center; border: 1px solid #1a1a1a;
        }
        .stat-card i { color: #00d2ff; font-size: 1.4rem; margin-bottom: 5px; }
        .stat-value { font-size: 1.2rem; font-weight: bold; display: block; }
        .stat-label { font-size: 10px; color: #555; text-transform: uppercase; letter-spacing: 1px; }

        .lb-title { font-weight: bold; margin-bottom: 15px; font-size: 1.1rem; color: #f1c40f; display: flex; align-items: center; gap: 8px; }
        .lb-item {
            display: flex; justify-content: space-between; align-items: center;
            background: #0a0a0a; padding: 12px; border-radius: 8px;
            margin-bottom: 8px; font-size: 0.9rem;
            border-left: 4px solid #00d2ff;
        }

        .toast-container { position: absolute; bottom: 30px; width: 80%; pointer-events: none; }
        .toast {
            background: #00d2ff; color: #000; padding: 12px 20px;
            border-radius: 50px; font-weight: 900; text-align: center;
            animation: slideUp 0.5s ease;
        }
        @keyframes slideUp { from { transform: translateY(50px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    </style>
</head>
<body>

<div id="start-overlay" onclick="launch()">
    <i class="fa-solid fa-play" style="font-size: 4rem; color: #00d2ff; margin-bottom: 20px;"></i>
    <h2 style="letter-spacing: 5px;">KLIK UNTUK FULLSCREEN</h2>
</div>

<div class="app-container">
    <div class="left-panel">
        <div class="status-badge"><i class="fa-solid fa-circle" id="dot" style="color: #555;"></i> <span id="status-text">Standby</span></div>
        <div class="title-game"><i class="fa-solid fa-brain"></i> TEBAK KATA</div>
        <div class="scrambled-box" id="word-display">......</div>
        <p style="color: #444; font-weight: bold;"><i class="fa-solid fa-comments"></i> KETIK JAWABAN DI LIVE CHAT!</p>
        <div class="toast-container" id="toast-wrap"></div>
    </div>
    
    <div class="right-panel">
        <div class="stats-grid">
            <div class="stat-card"><i class="fa-solid fa-users"></i><span class="stat-value" id="v-view">0</span><span class="stat-label">Viewers</span></div>
            <div class="stat-card"><i class="fa-solid fa-heart"></i><span class="stat-value" id="v-like">0</span><span class="stat-label">Likes</span></div>
            <div class="stat-card"><i class="fa-solid fa-message"></i><span class="stat-value" id="v-chat">0</span><span class="stat-label">Chat</span></div>
            <div class="stat-card"><i class="fa-solid fa-share"></i><span class="stat-value" id="v-share">0</span><span class="stat-label">Share</span></div>
        </div>
        <div class="lb-title"><i class="fa-solid fa-crown"></i> TOP PLAYERS</div>
        <div id="lb-content"></div>
    </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
    const socket = io();
    
    function launch() {
        document.getElementById('start-overlay').style.display = 'none';
        const el = document.documentElement;
        if (el.requestFullscreen) el.requestFullscreen();
        if (screen.orientation && screen.orientation.lock) screen.orientation.lock('landscape');
    }

    // PWA - Agar bisa di-install Chrome
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js');
    }

    socket.on('state_sync', (data) => {
        document.getElementById('word-display').innerText = data.scrambled_word;
        document.getElementById('status-text').innerText = data.status;
        document.getElementById('v-view').innerText = data.viewers;
        document.getElementById('v-like').innerText = data.likes;
        document.getElementById('v-chat').innerText = data.comments_count;
        document.getElementById('v-share').innerText = data.shares;
        if(data.status.includes("Connected")) document.getElementById('dot').style.color = '#2ecc71';
        renderLB(data.leaderboard);
    });

    socket.on('game_update', d => {
        document.getElementById('word-display').innerText = d.scrambled;
    });
    
    socket.on('correct_answer', d => {
        const tw = document.getElementById('toast-wrap');
        const t = document.createElement('div');
        t.className = 'toast';
        t.innerHTML = `<i class="fa-solid fa-check"></i> ${d.username.toUpperCase()} BENAR!`;
        tw.appendChild(t);
        setTimeout(() => t.remove(), 2500);
    });

    socket.on('stats_update', d => {
        if(d.viewers !== undefined) document.getElementById('v-view').innerText = d.viewers;
        if(d.likes !== undefined) document.getElementById('v-like').innerText = d.likes;
        if(d.comments_count !== undefined) document.getElementById('v-chat').innerText = d.comments_count;
        if(d.shares !== undefined) document.getElementById('v-share').innerText = d.shares;
    });

    socket.on('leaderboard_update', d => renderLB(d.leaderboard));

    function renderLB(lb) {
        const cont = document.getElementById('lb-content');
        cont.innerHTML = '';
        Object.entries(lb).sort((a,b) => b[1]-a[1]).slice(0,3).forEach(([u, s]) => {
            const name = u.length > 10 ? u.substring(0,10) + '..' : u;
            cont.innerHTML += `<div class="lb-item"><span>${name}</span><b>${s} Pts</b></div>`;
        });
    }
</script>
</body>
</html>
"""

MANIFEST_JSON = """
{
  "name": "TikTok Game Pro",
  "short_name": "TebakKata",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#000000",
  "theme_color": "#000000",
  "orientation": "landscape",
  "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/808/808439.png", "sizes": "512x512", "type": "image/png"}]
}
"""

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/manifest.json')
def manifest(): return Response(MANIFEST_JSON, mimetype='application/json')

@app.route('/sw.js')
def sw(): return Response("self.addEventListener('fetch', function(e){});", mimetype='application/javascript')

def start_tiktok():
    client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)
    
    @client.on(ConnectEvent)
    async def on_connect(_): 
        game_state["status"] = "Connected"
        socketio.emit('state_sync', game_state)

    @client.on(CommentEvent)
    async def on_comment(event):
        game_state["comments_count"] += 1
        jawaban = event.comment.strip().upper()
        
        # LOGIKA UNLIMITED: Cek jawaban, beri poin, lalu acak kata lagi
        if jawaban == game_state["current_word"]:
            user = event.user.nickname
            game_state["leaderboard"][user] = game_state["leaderboard"].get(user, 0) + 10
            socketio.emit('correct_answer', {"username": user})
            socketio.emit('leaderboard_update', {"leaderboard": game_state["leaderboard"]})
            # Langsung panggil acak_kata buat soal berikutnya
            acak_kata()
            
        socketio.emit('stats_update', {"comments_count": game_state["comments_count"]})

    @client.on(LikeEvent)
    async def on_like(event):
        game_state["likes"] += event.like_count
        socketio.emit('stats_update', {"likes": game_state["likes"]})

    @client.on(RoomUserSeqEvent)
    async def on_v(event):
        game_state["viewers"] = event.viewer_count
        socketio.emit('stats_update', {"viewers": game_state["viewers"]})

    async def run_forever():
        while True:
            try: 
                await client.start()
            except Exception as e:
                game_state["status"] = "Offline / Standby"
                socketio.emit('state_sync', game_state)
                await asyncio.sleep(10)
    
    asyncio.new_event_loop().run_until_complete(run_forever())

if __name__ == '__main__':
    threading.Thread(target=start_tiktok, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)
