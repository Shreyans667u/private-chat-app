/* chat.js - minimal client wiring to Socket.IO and UI interactions.
   Extend with group join requests, read receipts, and server API calls.
*/

const socket = io(); // uses same origin
const username = window.NG && window.NG.username ? window.NG.username : "Anon";

let currentRoom = null;
const messagesEl = document.getElementById('messages');
const groupList = document.getElementById('groupList');
const memberList = document.getElementById('memberList');
const currentRoomTitle = document.getElementById('currentRoomTitle');
const requestsCount = document.getElementById('requestsCount');
const requestsList = document.getElementById('requestsList');

// Helpers
function el(tag, cls = ''){ const e = document.createElement(tag); if(cls) e.className = cls; return e; }
function appendMessage(text, fromMe=false, meta=''){ const li = el('li', 'message' + (fromMe? ' me':'')); if(meta){ const m = el('div','meta'); m.textContent = meta; li.appendChild(m);} li.appendChild(document.createTextNode(text)); messagesEl.appendChild(li); messagesEl.scrollTop = messagesEl.scrollHeight; }

// Clicking group list -> join room
groupList.addEventListener('click', (ev)=>{
  const item = ev.target.closest('.group-item');
  if(!item) return;
  const room = item.dataset.room;
  joinRoom(room);
});

function joinRoom(room){
  if(currentRoom) socket.emit('leave_room', {room: currentRoom}); // optional leave event on server
  currentRoom = room;
  currentRoomTitle.textContent = room;
  messagesEl.innerHTML = '';
  memberList.innerHTML = '';
  socket.emit('join_group', {room, username});
  // fetch members & past messages via REST (implement server endpoints) - placeholder:
  fetch(`/api/group/${encodeURIComponent(room)}/history`).then(r=>r.json()).then(data=>{
    if(data && data.messages) data.messages.forEach(m=>{
      appendMessage(m.text, m.sender === username, `${m.sender} • ${new Date(m.ts).toLocaleTimeString()}`);
    });
    if(data && data.members){
      data.members.forEach(u=>{
        const mi = el('div','member');
        mi.innerHTML = `<div class="avatar">${u[0].toUpperCase()}</div><div>${u} <div class="status"><span class="status-dot ${u.online? 'online':'offline'}"></span></div></div>`;
        memberList.appendChild(mi);
      });
    }
  }).catch(()=>{ /* ignore if endpoint not ready */ });
}

// Send message
document.getElementById('sendBtn').addEventListener('click', ()=>{
  const input = document.getElementById('msgInput');
  const text = input.value.trim();
  if(!text || !currentRoom) return;
  const payload = {room: currentRoom, username, text};
  socket.emit('send_message', payload);
  appendMessage(text, true, `You • ${new Date().toLocaleTimeString()}`);
  input.value = '';
});

// Receive forwarded messages
socket.on('receive_message', (data)=>{
  if(data.room && data.room !== currentRoom) {
    // optionally show unread badge per group (not implemented)
    return;
  }
  appendMessage(data.text, data.username === username, `${data.username} • ${new Date().toLocaleTimeString()}`);
});

// Requests & modals
document.getElementById('newGroupBtn').addEventListener('click', ()=>document.getElementById('modal').classList.remove('hidden'));
document.getElementById('createGroupCancel').addEventListener('click', ()=>document.getElementById('modal').classList.add('hidden'));
document.getElementById('createGroupConfirm').addEventListener('click', ()=>{
  const name = document.getElementById('newGroupName').value.trim();
  if(!name) return alert('Enter a group name');
  fetch('/create_group', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:`group_name=${encodeURIComponent(name)}`})
    .then(()=> location.reload());
});

// join requests modal open
document.getElementById('requestsBtn').addEventListener('click', ()=>{
  document.getElementById('requestsModal').classList.remove('hidden');
});
// close
document.getElementById('closeRequests').addEventListener('click', ()=>document.getElementById('requestsModal').classList.add('hidden'));

// live online status: ask server to notify you of online users for current room
socket.on('user_online', (u)=>{/* update member status */});
socket.on('user_offline', (u)=>{/* update member status */});
