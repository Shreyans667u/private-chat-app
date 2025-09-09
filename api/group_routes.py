# api/group_routes.py
from flask import request, jsonify, session
from . import api_bp
from app import db, User, Group

# Dummy in-memory storage for messages (replace with DB later)
messages_store = {}  # {room_name: [{text, sender, ts}]}
join_requests = {}   # {room_name: [username1, username2]}

# --------- Get group message history and members ---------
@api_bp.route('/group/<room_name>/history', methods=['GET'])
def group_history(room_name):
    room = Group.query.filter_by(name=room_name).first()
    if not room:
        return jsonify({'error': 'Group not found'}), 404

    # Messages
    msgs = messages_store.get(room_name, [])
    
    # Members: all users who have approved membership
    members = []
    users = User.query.all()  # for simplicity; in real DB, join table
    for u in users:
        members.append({'name': u.username, 'online': False})  # online status optional

    return jsonify({'messages': msgs, 'members': members})

# --------- Send join request ---------
@api_bp.route('/group/<room_name>/join', methods=['POST'])
def join_group():
    room_name = request.form.get('room_name')
    if 'username' not in session:
        return jsonify({'error': 'Login required'}), 401

    username = session['username']
    if room_name not in join_requests:
        join_requests[room_name] = []
    if username not in join_requests[room_name]:
        join_requests[room_name].append(username)
    return jsonify({'status': 'requested'})

# --------- Get pending join requests (admin only) ---------
@api_bp.route('/group/<room_name>/requests', methods=['GET'])
def get_requests(room_name):
    if 'username' not in session:
        return jsonify({'error': 'Login required'}), 401
    # In real DB, check if session['username'] is admin of group
    pending = join_requests.get(room_name, [])
    return jsonify({'requests': pending})

# --------- Approve join request (admin only) ---------
@api_bp.route('/group/<room_name>/approve', methods=['POST'])
def approve_request(room_name):
    username_to_approve = request.form.get('username')
    if room_name not in join_requests or username_to_approve not in join_requests[room_name]:
        return jsonify({'error': 'No such request'}), 404

    join_requests[room_name].remove(username_to_approve)
    # Add to actual members table in DB (not implemented here)
    return jsonify({'status': f'{username_to_approve} approved'})
