// DeceMSG - Frontend Application

class DeceMSGApp {
    constructor() {
        this.apiBase = '/api';
        this.token = localStorage.getItem('token');
        this.currentUser = null;
        this.chats = [];
        this.currentChat = null;
        this.ws = null;
        this.searchResults = [];
        
        this.init();
    }

    init() {
        // Check authentication
        if (this.token) {
            this.showMainScreen();
            this.loadCurrentUser();
        } else {
            this.showLoginScreen();
        }
        
        this.bindEvents();
    }

    bindEvents() {
        // Login form
        document.getElementById('login-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        // New chat button
        document.getElementById('btn-new-chat').addEventListener('click', () => {
            this.showNewChatModal();
        });

        // Settings button
        document.getElementById('btn-settings').addEventListener('click', () => {
            this.toggleAdminPanel();
        });

        // Send message
        document.getElementById('btn-send').addEventListener('click', () => {
            this.sendMessage();
        });

        document.getElementById('message-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Search chats
        document.getElementById('search-chats').addEventListener('input', (e) => {
            this.filterChats(e.target.value);
        });

        // Modal close buttons
        document.getElementById('btn-close-modal').addEventListener('click', () => {
            this.hideNewChatModal();
        });

        document.getElementById('btn-cancel-chat').addEventListener('click', () => {
            this.hideNewChatModal();
        });

        document.getElementById('btn-start-chat').addEventListener('click', () => {
            this.startNewChat();
        });

        // Chat type toggle
        document.getElementById('btn-direct-chat').addEventListener('click', () => {
            this.setChatType('direct');
        });

        document.getElementById('btn-group-chat').addEventListener('click', () => {
            this.setChatType('group');
        });

        // Admin panel
        document.getElementById('btn-close-admin').addEventListener('click', () => {
            this.toggleAdminPanel();
        });

        // Admin tabs
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Create user
        document.getElementById('btn-create-user').addEventListener('click', () => {
            this.showCreateUserModal();
        });

        document.getElementById('btn-close-user-modal').addEventListener('click', () => {
            this.hideCreateUserModal();
        });

        document.getElementById('create-user-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createUser();
        });

        // Save config
        document.getElementById('btn-save-config').addEventListener('click', () => {
            this.saveConfig();
        });

        // Search users in admin
        document.getElementById('search-users').addEventListener('input', (e) => {
            this.loadUsers(e.target.value);
        });

        // Back button (mobile)
        document.getElementById('btn-back').addEventListener('click', () => {
            document.getElementById('sidebar').classList.remove('hidden');
            document.getElementById('chat-content').classList.add('hidden');
        });
    }

    // API Helpers
    async apiCall(endpoint, method = 'GET', body = null) {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const options = { method, headers };
        
        if (body && method !== 'GET') {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(`${this.apiBase}${endpoint}`, options);
        
        if (response.status === 401) {
            this.logout();
            throw new Error('Unauthorized');
        }

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'API Error');
        }

        return data;
    }

    // Authentication
    async handleLogin() {
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        const errorEl = document.getElementById('login-error');

        try {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const response = await fetch(`${this.apiBase}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: formData
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Login failed');
            }

            this.token = data.access_token;
            localStorage.setItem('token', this.token);
            
            await this.loadCurrentUser();
            this.showMainScreen();
            errorEl.classList.add('hidden');

        } catch (error) {
            errorEl.textContent = error.message;
            errorEl.classList.remove('hidden');
        }
    }

    logout() {
        this.token = null;
        localStorage.removeItem('token');
        this.currentUser = null;
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        this.showLoginScreen();
    }

    async loadCurrentUser() {
        try {
            this.currentUser = await this.apiCall('/auth/me');
            this.connectWebSocket();
            this.loadChats();
            
            if (this.currentUser.is_admin) {
                this.loadAdminConfig();
            }
        } catch (error) {
            console.error('Failed to load current user:', error);
            this.logout();
        }
    }

    // Screens
    showLoginScreen() {
        document.getElementById('login-screen').classList.add('active');
        document.getElementById('main-screen').classList.remove('active');
    }

    showMainScreen() {
        document.getElementById('login-screen').classList.remove('active');
        document.getElementById('main-screen').classList.add('active');
    }

    // WebSocket
    connectWebSocket() {
        if (this.ws) {
            this.ws.close();
        }

        const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws?token=${this.token}`;
        
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            // Join all chat rooms
            this.chats.forEach(chat => {
                this.ws.send(JSON.stringify({
                    type: 'join_chat',
                    chat_id: chat.id
                }));
            });
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            // Reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'new_message':
                this.handleNewMessage(data.message, data.chat_id);
                break;
            case 'reaction_update':
                this.updateMessageReactions(data);
                break;
            case 'presence':
                this.updatePresence(data.user_id, data.is_online);
                break;
            case 'typing':
                this.showTypingIndicator(data);
                break;
            case 'read_receipt':
                this.updateReadReceipt(data);
                break;
        }
    }

    handleNewMessage(message, chatId) {
        if (this.currentChat && this.currentChat.id === chatId) {
            this.appendMessage(message);
            this.scrollToBottom();
        }
        
        // Update chat list
        this.loadChats();
    }

    // Chats
    async loadChats() {
        try {
            this.chats = await this.apiCall('/chats');
            this.renderChatList();
        } catch (error) {
            console.error('Failed to load chats:', error);
        }
    }

    renderChatList() {
        const container = document.getElementById('chat-list');
        container.innerHTML = '';

        this.chats.forEach(chat => {
            const chatEl = this.createChatElement(chat);
            container.appendChild(chatEl);
        });
    }

    createChatElement(chat) {
        const div = document.createElement('div');
        div.className = 'chat-item';
        div.dataset.chatId = chat.id;
        
        // Get chat name
        let name = chat.name;
        let avatar = '';
        
        if (chat.type === 'direct') {
            const otherMember = chat.members.find(m => m.user_id !== this.currentUser?.id);
            if (otherMember?.user) {
                name = otherMember.user.display_name || otherMember.user.username;
                avatar = this.getInitials(name);
            }
        } else {
            avatar = chat.name ? this.getInitials(chat.name) : '?';
        }

        const lastMessage = chat.last_message;
        const preview = lastMessage ? this.truncate(lastMessage.content, 40) : 'No messages yet';

        div.innerHTML = `
            <div class="avatar">${avatar}</div>
            <div class="chat-item-info">
                <div class="chat-item-header">
                    <span class="chat-item-name">${this.escapeHtml(name || 'Unknown')}</span>
                    <span class="chat-item-time">${this.formatTime(lastMessage?.created_at)}</span>
                </div>
                <div class="chat-item-preview">
                    ${this.escapeHtml(preview)}
                    ${chat.unread_count > 0 ? `<span class="unread-badge">${chat.unread_count}</span>` : ''}
                </div>
            </div>
        `;

        div.addEventListener('click', () => this.openChat(chat));

        return div;
    }

    filterChats(query) {
        const items = document.querySelectorAll('.chat-item');
        const lowerQuery = query.toLowerCase();

        items.forEach(item => {
            const name = item.querySelector('.chat-item-name').textContent.toLowerCase();
            item.style.display = name.includes(lowerQuery) ? 'flex' : 'none';
        });
    }

    async openChat(chat) {
        this.currentChat = chat;
        
        // Update UI
        document.querySelectorAll('.chat-item').forEach(el => {
            el.classList.toggle('active', el.dataset.chatId === chat.id);
        });

        // Show chat content
        document.getElementById('no-chat-selected').classList.add('hidden');
        document.getElementById('chat-content').classList.remove('hidden');

        // Update header
        const nameEl = document.getElementById('chat-name');
        const statusEl = document.getElementById('chat-status');
        
        if (chat.type === 'direct') {
            const otherMember = chat.members.find(m => m.user_id !== this.currentUser?.id);
            if (otherMember?.user) {
                nameEl.textContent = otherMember.user.display_name || otherMember.user.username;
                statusEl.textContent = this.searchResults[otherMember.user_id]?.is_online ? 'online' : 'offline';
                statusEl.className = this.searchResults[otherMember.user_id]?.is_online ? 'online' : '';
            }
        } else {
            nameEl.textContent = chat.name || 'Group Chat';
            statusEl.textContent = `${chat.members.length} members`;
            statusEl.className = '';
        }

        // Load messages
        await this.loadMessages(chat.id);

        // Join WebSocket room
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'join_chat',
                chat_id: chat.id
            }));
        }

        // Mobile: hide sidebar
        if (window.innerWidth <= 768) {
            document.getElementById('sidebar').classList.add('hidden');
        }
    }

    async loadMessages(chatId) {
        try {
            const messages = await this.apiCall(`/chats/${chatId}/messages`);
            this.renderMessages(messages);
            this.scrollToBottom();
        } catch (error) {
            console.error('Failed to load messages:', error);
        }
    }

    renderMessages(messages) {
        const container = document.getElementById('messages-container');
        container.innerHTML = '';

        messages.forEach(msg => {
            this.appendMessage(msg);
        });
    }

    appendMessage(msg) {
        const container = document.getElementById('messages-container');
        const div = document.createElement('div');
        div.className = `message ${msg.sender_id === this.currentUser?.id ? 'sent' : 'received'}`;
        div.dataset.messageId = msg.id;

        const senderName = msg.sender?.display_name || msg.sender?.username || 'Unknown';
        const isCurrentUser = msg.sender_id === this.currentUser?.id;

        let reactionsHtml = '';
        if (msg.reactions && Object.keys(msg.reactions).length > 0) {
            const reactions = Object.entries(msg.reactions)
                .map(([emoji, data]) => `<span class="reaction-badge">${emoji} ${data.count}</span>`)
                .join('');
            reactionsHtml = `<div class="message-reactions">${reactions}</div>`;
        }

        div.innerHTML = `
            ${!isCurrentUser ? `<div class="message-header"><span class="message-sender">${this.escapeHtml(senderName)}</span></div>` : ''}
            <div class="message-content">${this.escapeHtml(msg.content)}</div>
            <div class="message-footer">
                <span class="message-time">${this.formatTime(msg.created_at)}</span>
            </div>
            ${reactionsHtml}
        `;

        container.appendChild(div);
    }

    async sendMessage() {
        const input = document.getElementById('message-input');
        const content = input.value.trim();

        if (!content || !this.currentChat) return;

        try {
            await this.apiCall(`/chats/${this.currentChat.id}/messages`, 'POST', {
                content,
                message_type: 'text'
            });

            input.value = '';
            await this.loadMessages(this.currentChat.id);

        } catch (error) {
            console.error('Failed to send message:', error);
        }
    }

    // New Chat Modal
    showNewChatModal() {
        document.getElementById('new-chat-modal').classList.remove('hidden');
    }

    hideNewChatModal() {
        document.getElementById('new-chat-modal').classList.add('hidden');
        document.getElementById('new-chat-username').value = '';
        document.getElementById('group-name').value = '';
        document.getElementById('group-members').value = '';
    }

    setChatType(type) {
        const directBtn = document.getElementById('btn-direct-chat');
        const groupBtn = document.getElementById('btn-group-chat');
        const directForm = document.getElementById('direct-chat-form');
        const groupForm = document.getElementById('group-chat-form');

        if (type === 'direct') {
            directBtn.classList.add('active');
            groupBtn.classList.remove('active');
            directForm.classList.remove('hidden');
            groupForm.classList.add('hidden');
        } else {
            directBtn.classList.remove('active');
            groupBtn.classList.add('active');
            directForm.classList.add('hidden');
            groupForm.classList.remove('hidden');
        }
    }

    async startNewChat() {
        const directBtn = document.getElementById('btn-direct-chat');
        
        try {
            if (directBtn.classList.contains('active')) {
                // Direct message
                const username = document.getElementById('new-chat-username').value.trim();
                if (!username) {
                    alert('Please enter a username');
                    return;
                }

                // Parse username#domain format
                let targetUsername = username;
                let targetDomain = this.currentUser?.domain || 'localhost';
                
                if (username.includes('#')) {
                    const parts = username.split('#');
                    targetUsername = parts[0];
                    targetDomain = parts[1];
                }

                // Search for user
                const users = await this.apiCall(`/users/search?q=${targetUsername}`);
                const targetUser = users.find(u => 
                    u.username === targetUsername && 
                    (u.domain === targetDomain || u.domain === 'localhost')
                );

                if (!targetUser) {
                    // Check if local user
                    if (targetDomain === this.currentUser?.domain || targetDomain === 'localhost') {
                        alert('User not found');
                        return;
                    }
                    // For federated users, we'd need to look them up via federation
                    alert('User not found on this server');
                    return;
                }

                const chat = await this.apiCall('/chats', 'POST', {
                    type: 'direct',
                    member_ids: [targetUser.id]
                });

                this.hideNewChatModal();
                this.loadChats();
                this.openChat(chat);

            } else {
                // Group chat
                const groupName = document.getElementById('group-name').value.trim();
                const membersInput = document.getElementById('group-members').value.trim();

                if (!groupName) {
                    alert('Please enter a group name');
                    return;
                }

                // Parse member list
                const memberUsernames = membersInput.split(',').map(m => m.trim()).filter(m => m);
                
                // For now, we'll create a group without member validation
                const chat = await this.apiCall('/chats', 'POST', {
                    type: 'group',
                    name: groupName,
                    member_ids: []
                });

                this.hideNewChatModal();
                this.loadChats();
                this.openChat(chat);
            }
        } catch (error) {
            console.error('Failed to start chat:', error);
            alert(error.message);
        }
    }

    // Admin Panel
    toggleAdminPanel() {
        const panel = document.getElementById('admin-panel');
        panel.classList.toggle('hidden');
        
        if (!panel.classList.contains('hidden')) {
            this.loadUsers();
            this.loadStats();
        }
    }

    switchTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabName}`);
        });
    }

    async loadUsers(search = '') {
        try {
            const data = await this.apiCall(`/users?search=${search}`);
            this.renderUserList(data.users);
        } catch (error) {
            console.error('Failed to load users:', error);
        }
    }

    renderUserList(users) {
        const container = document.getElementById('user-list');
        container.innerHTML = '';

        users.forEach(user => {
            const div = document.createElement('div');
            div.className = 'user-item';
            div.innerHTML = `
                <div class="avatar">${this.getInitials(user.display_name)}</div>
                <div class="user-item-info">
                    <div class="user-item-name">${this.escapeHtml(user.display_name)}</div>
                    <div class="user-item-email">@${this.escapeHtml(user.username)}#${this.escapeHtml(user.domain)}</div>
                </div>
                <div class="user-item-actions">
                    ${user.is_active ? 
                        `<button class="btn-secondary" onclick="app.deactivateUser('${user.id}')">Deactivate</button>` :
                        `<button class="btn-primary" onclick="app.activateUser('${user.id}')">Activate</button>`
                    }
                </div>
            `;
            container.appendChild(div);
        });
    }

    async createUser() {
        const username = document.getElementById('new-user-username').value.trim();
        const displayName = document.getElementById('new-user-display-name').value.trim();
        const password = document.getElementById('new-user-password').value;
        const isAdmin = document.getElementById('new-user-is-admin').checked;

        try {
            await this.apiCall('/users', 'POST', {
                username,
                display_name: displayName,
                password,
                is_admin: isAdmin
            });

            this.hideCreateUserModal();
            this.loadUsers();
        } catch (error) {
            alert(error.message);
        }
    }

    async deactivateUser(userId) {
        try {
            await this.apiCall(`/users/${userId}`, 'PUT', { is_active: false });
            this.loadUsers(document.getElementById('search-users').value);
        } catch (error) {
            alert(error.message);
        }
    }

    async activateUser(userId) {
        try {
            await this.apiCall(`/users/${userId}`, 'PUT', { is_active: true });
            this.loadUsers(document.getElementById('search-users').value);
        } catch (error) {
            alert(error.message);
        }
    }

    showCreateUserModal() {
        document.getElementById('create-user-modal').classList.remove('hidden');
    }

    hideCreateUserModal() {
        document.getElementById('create-user-modal').classList.add('hidden');
        document.getElementById('create-user-form').reset();
    }

    async loadAdminConfig() {
        try {
            const config = await this.apiCall('/admin/config');
            document.getElementById('config-public-registration').checked = config.allow_public_registration;
            document.getElementById('config-user-group-creation').checked = config.allow_user_group_creation;
            document.getElementById('config-keep-history').checked = config.default_keep_history;
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }

    async saveConfig() {
        try {
            await this.apiCall('/admin/config', 'PUT', {
                allow_public_registration: document.getElementById('config-public-registration').checked,
                allow_user_group_creation: document.getElementById('config-user-group-creation').checked,
                default_keep_history: document.getElementById('config-keep-history').checked
            });
            alert('Settings saved!');
        } catch (error) {
            alert(error.message);
        }
    }

    async loadStats() {
        try {
            const stats = await this.apiCall('/admin/stats');
            this.renderStats(stats);
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    renderStats(stats) {
        const container = document.getElementById('server-stats');
        container.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${stats.total_users}</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.active_users_24h}</div>
                <div class="stat-label">Active (24h)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.total_chats}</div>
                <div class="stat-label">Total Chats</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.total_messages}</div>
                <div class="stat-label">Total Messages</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.active_users_7d}</div>
                <div class="stat-label">Active (7d)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.storage_used_mb} MB</div>
                <div class="stat-label">Storage Used</div>
            </div>
        `;
    }

    // Utility Methods
    getInitials(name) {
        if (!name) return '?';
        return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncate(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.slice(0, maxLength) + '...';
    }

    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        const now = new Date();
        
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        
        if (date.toDateString() === yesterday.toDateString()) {
            return 'Yesterday';
        }
        
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }

    scrollToBottom() {
        const container = document.getElementById('messages-container');
        container.scrollTop = container.scrollHeight;
    }

    updateMessageReactions(data) {
        // Handle reaction updates
        this.loadMessages(this.currentChat?.id);
    }

    updatePresence(userId, isOnline) {
        this.searchResults[userId] = { is_online: isOnline };
        
        if (this.currentChat) {
            const otherMember = this.currentChat.members.find(m => m.user_id === userId);
            if (otherMember) {
                const statusEl = document.getElementById('chat-status');
                if (userId === otherMember.user_id) {
                    statusEl.textContent = isOnline ? 'online' : 'offline';
                    statusEl.className = isOnline ? 'online' : '';
                }
            }
        }
    }

    showTypingIndicator(data) {
        // Could show "typing..." indicator
    }

    updateReadReceipt(data) {
        // Handle read receipts
    }
}

// Initialize app
const app = new DeceMSGApp();
