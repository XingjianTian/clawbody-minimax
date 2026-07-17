"""心宠的中文 Gradio 控制台。"""

import asyncio
import base64
import logging
import threading
from html import escape
from pathlib import Path

import gradio as gr

logger = logging.getLogger(__name__)


UI_CSS = """
:root {
    color-scheme: light;
    --canvas: #f5f5f7;
    --surface: #fcfcfd;
    --control: #ececf0;
    --ink: #1d1d1f;
    --ink-secondary: #515154;
    --ink-muted: #6e6e73;
    --line: #d2d2d7;
    --line-strong: #a8a8ad;
    --signal: #e49b0f;
    --signal-deep: #8a5700;
    --signal-soft: #fff6e5;
    --success: #16734b;
    --success-soft: #eaf7f0;
    --danger: #b42318;
    --danger-soft: #fdedea;
    --ease-out: cubic-bezier(.16, 1, .3, 1);
    --body-text-color: var(--ink);
    --body-text-color-subdued: var(--ink-secondary);
    --block-title-text-color: var(--ink);
    --block-label-text-color: var(--ink-secondary);
    --block-background-fill: var(--surface);
    --block-border-color: var(--line);
    --input-background-fill: var(--control);
    --input-border-color: transparent;
    --background-fill-primary: var(--canvas);
    --background-fill-secondary: var(--surface);
    --icon-play: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpolygon points='6 3 20 12 6 21 6 3' fill='black'/%3E%3C/svg%3E");
    --icon-square: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect x='5' y='5' width='14' height='14' rx='1' fill='black'/%3E%3C/svg%3E");
    --icon-save: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z' fill='none' stroke='black' stroke-width='2'/%3E%3Cpath d='M17 21v-8H7v8M7 3v5h8' fill='none' stroke='black' stroke-width='2'/%3E%3C/svg%3E");
    --icon-check: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='m20 6-11 11-5-5' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    --icon-search: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ccircle cx='11' cy='11' r='8' fill='none' stroke='%23515154' stroke-width='2'/%3E%3Cpath d='m21 21-4.3-4.3' fill='none' stroke='%23515154' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E");
    --icon-mic: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z' fill='none' stroke='black' stroke-width='2'/%3E%3Cpath d='M19 10v2a7 7 0 0 1-14 0v-2M12 19v3' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E");
    --icon-message: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z' fill='none' stroke='black' stroke-width='2' stroke-linejoin='round'/%3E%3C/svg%3E");
    --icon-volume: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M11 5 6 9H2v6h4l5 4Z' fill='none' stroke='black' stroke-width='2' stroke-linejoin='round'/%3E%3Cpath d='M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E");
    --icon-motion: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M3 12h4l2-7 4 14 2-7h6' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
}

html, body {
    width: 100% !important;
    min-width: 100% !important;
    min-height: 100% !important;
    margin: 0 !important;
    overflow-x: hidden !important;
    background: var(--canvas) !important;
}

gradio-app {
    display: block !important;
    width: 100% !important;
    min-width: 100vw !important;
    min-height: 100dvh !important;
    background: var(--canvas) !important;
}

div.gradio-container {
    box-sizing: border-box !important;
    width: 100% !important;
    max-width: none !important;
    min-height: 100dvh !important;
    margin: 0 !important;
    padding: 0 max(clamp(16px, 3.125vw, 32px), calc((100vw - 1440px) / 2)) 64px !important;
    overflow-x: clip !important;
    background: var(--canvas) !important;
    color: var(--ink) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif !important;
    font-size: 17px !important;
    line-height: 1.65 !important;
}

div.gradio-container main.app {
    padding: 0 !important;
}

#app-shell {
    width: 100% !important;
    max-width: 1440px !important;
    margin: 0 auto !important;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}

#topbar {
    margin: 0 !important;
    border: 0 !important;
    background: transparent !important;
}

.device-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 32px;
    min-height: 98px;
    border-bottom: 1px solid var(--line);
}

.device-brand {
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0;
}

.device-brand__mark {
    display: grid;
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
    place-items: center;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--surface);
    color: var(--ink);
}

.device-brand__mark svg {
    width: 24px;
    height: 24px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}

.device-brand__mark img {
    display: block;
    width: 100%;
    height: 100%;
    border-radius: 7px;
    object-fit: cover;
}

.device-brand__name,
.device-brand__title,
.device-state__primary,
.device-state__secondary {
    margin: 0;
    letter-spacing: 0;
}

.device-brand__name {
    color: var(--ink-secondary);
    font-size: 14px;
    font-weight: 600;
    line-height: 1.35;
}

.device-brand__title {
    color: var(--ink);
    font-size: 22px;
    font-weight: 700;
    line-height: 1.3;
}

.device-state {
    display: flex;
    align-items: center;
    gap: 11px;
    min-width: 0;
}

.device-state__dot {
    width: 10px;
    height: 10px;
    flex: 0 0 10px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 0 4px rgb(22 115 75 / .12);
}

.device-state__copy {
    display: grid;
    gap: 1px;
    text-align: right;
}

.device-state__primary {
    color: var(--ink);
    font-size: 15px;
    font-weight: 650;
    line-height: 1.35;
}

.device-state__secondary {
    color: var(--ink-secondary);
    font-size: 14px;
    line-height: 1.35;
}

#main-tabs {
    margin-top: 22px !important;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}

#main-tabs [role="tablist"] {
    display: flex !important;
    gap: 24px !important;
    min-height: 49px !important;
    margin: 0 0 28px !important;
    padding: 0 !important;
    overflow-x: auto !important;
    border: 0 !important;
    border-bottom: 1px solid var(--line) !important;
    border-radius: 0 !important;
    background: transparent !important;
    scrollbar-width: none;
}

#main-tabs [role="tablist"]::-webkit-scrollbar {
    display: none;
}

#main-tabs [role="tab"] {
    position: relative !important;
    min-width: max-content !important;
    min-height: 48px !important;
    padding: 0 2px !important;
    border: 0 !important;
    border-radius: 0 !important;
    background: transparent !important;
    color: var(--ink-secondary) !important;
    font-size: 17px !important;
    font-weight: 650 !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
    transition: color 180ms var(--ease-out) !important;
}

#main-tabs [role="tab"]::after {
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    height: 2px;
    border-radius: 2px 2px 0 0;
    background: var(--signal);
    content: "";
    opacity: 0;
    transform: scaleX(.35);
    transition: opacity 180ms var(--ease-out), transform 180ms var(--ease-out);
}

#main-tabs [role="tab"]:hover {
    color: var(--ink) !important;
}

#main-tabs [role="tab"][aria-selected="true"] {
    color: var(--ink) !important;
}

#main-tabs [role="tab"][aria-selected="true"]::after {
    opacity: 1;
    transform: scaleX(1);
}

#main-tabs [role="tab"]:focus-visible {
    outline: 2px solid var(--signal-deep) !important;
    outline-offset: -2px !important;
}

#main-tabs [role="tabpanel"] {
    padding: 0 !important;
    border: 0 !important;
    background: transparent !important;
}

.page-intro {
    margin: 0 0 24px;
}

.page-intro h2,
.page-intro p {
    margin: 0;
    letter-spacing: 0;
}

.page-intro h2 {
    color: var(--ink);
    font-size: 30px;
    font-weight: 700;
    line-height: 1.25;
}

.page-intro p {
    max-width: 70ch;
    margin-top: 7px;
    color: var(--ink-secondary);
    font-size: 17px;
    line-height: 1.65;
}

#conversation-layout {
    align-items: stretch !important;
    gap: 24px !important;
}

#conversation-main,
#session-side,
#identity-main,
#settings-main,
#about-main {
    min-width: 0 !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    background: var(--surface) !important;
    box-shadow: none !important;
}

#conversation-main,
#identity-main,
#settings-main,
#about-main {
    padding: 28px !important;
}

#session-side {
    padding: 24px !important;
}

.section-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 18px;
}

.section-heading h2,
.section-heading h3,
.section-heading p {
    margin: 0;
    letter-spacing: 0;
}

.section-heading h2 {
    color: var(--ink);
    font-size: 26px;
    font-weight: 700;
    line-height: 1.3;
}

.section-heading h3 {
    color: var(--ink);
    font-size: 20px;
    font-weight: 650;
    line-height: 1.4;
}

.section-heading p {
    color: var(--ink-secondary);
    font-size: 15px;
    line-height: 1.5;
}

#control-actions {
    align-items: stretch !important;
    gap: 12px !important;
    margin: 0 0 14px !important;
    padding: 0 !important;
    border: 0 !important;
}

.command-button {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 10px !important;
    min-height: 52px !important;
    padding: 0 24px !important;
    border-radius: 8px !important;
    font-size: 17px !important;
    font-weight: 650 !important;
    letter-spacing: 0 !important;
    transition: background-color 180ms var(--ease-out), border-color 180ms var(--ease-out),
                color 180ms var(--ease-out), transform 180ms var(--ease-out), box-shadow 180ms var(--ease-out) !important;
}

.command-button::before {
    width: 20px;
    height: 20px;
    flex: 0 0 20px;
    background: currentColor;
    content: "";
    -webkit-mask: var(--command-icon) center / contain no-repeat;
    mask: var(--command-icon) center / contain no-repeat;
}

.command-button:focus-visible {
    outline: 0 !important;
    box-shadow: 0 0 0 3px rgb(228 155 15 / .28) !important;
}

.command-button:active {
    transform: scale(.98) !important;
}

#start-conversation,
#apply-profile,
#save-profile {
    border: 1px solid var(--ink) !important;
    background: var(--ink) !important;
    color: var(--surface) !important;
}

#start-conversation:hover,
#apply-profile:hover,
#save-profile:hover {
    border-color: #353538 !important;
    background: #353538 !important;
}

#stop-conversation {
    border: 1px solid var(--line) !important;
    background: var(--surface) !important;
    color: var(--ink) !important;
}

#stop-conversation:hover {
    border-color: var(--line-strong) !important;
    background: var(--canvas) !important;
}

#start-conversation { --command-icon: var(--icon-play); }
#stop-conversation { --command-icon: var(--icon-square); }
#apply-profile { --command-icon: var(--icon-check); }
#save-profile { --command-icon: var(--icon-save); }

#conversation-status,
#profile-status,
#save-status {
    position: relative !important;
    min-height: 48px !important;
    margin: 0 !important;
    padding: 12px 16px 12px 42px !important;
    border: 1px solid #ead7b1 !important;
    border-radius: 8px !important;
    background: var(--signal-soft) !important;
    color: var(--signal-deep) !important;
    box-shadow: none !important;
}

#conversation-status::before,
#profile-status::before,
#save-status::before {
    position: absolute;
    top: 50%;
    left: 17px;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--signal);
    box-shadow: 0 0 0 4px rgb(228 155 15 / .14);
    content: "";
    transform: translateY(-50%);
}

#conversation-status .prose,
#profile-status .prose,
#save-status .prose,
#conversation-status p,
#profile-status p,
#save-status p {
    margin: 0 !important;
    color: inherit !important;
    font-size: 15px !important;
    font-weight: 650 !important;
    line-height: 1.45 !important;
}

.conversation-live #conversation-status {
    border-color: #b9ddca !important;
    background: var(--success-soft) !important;
    color: var(--success) !important;
}

.conversation-live #conversation-status::before {
    background: var(--success);
    box-shadow: 0 0 0 4px rgb(22 115 75 / .12);
}

#transcript {
    min-height: 520px !important;
    margin-top: 16px !important;
    overflow: hidden !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    background: var(--canvas) !important;
    box-shadow: none !important;
}

#transcript .wrap,
#transcript .bubble-wrap,
#transcript .placeholder-content,
#transcript .placeholder {
    background: var(--canvas) !important;
    color: var(--ink) !important;
}

#transcript .placeholder-content p,
#transcript .placeholder-content strong {
    color: var(--ink) !important;
}

#transcript .message,
#transcript .message p,
#transcript .message span {
    color: var(--ink) !important;
    font-size: 17px !important;
    line-height: 1.65 !important;
    letter-spacing: 0 !important;
}

#transcript .message {
    max-width: min(72ch, 88%) !important;
    border-radius: 8px !important;
}

#transcript .message.user,
#transcript [data-testid="user"] {
    background: var(--control) !important;
}

#transcript .message.bot,
#transcript [data-testid="bot"] {
    border: 1px solid var(--line) !important;
    background: var(--surface) !important;
}

.config-panel__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding-bottom: 17px;
    border-bottom: 1px solid var(--line);
}

.config-panel__head h3,
.config-panel__head p {
    margin: 0;
}

.config-panel__head h3 {
    color: var(--ink);
    font-size: 20px;
    font-weight: 650;
    line-height: 1.4;
}

.config-panel__head p {
    color: var(--ink-secondary);
    font-size: 14px;
}

.config-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 32px;
    padding: 0 10px;
    border-radius: 8px;
    background: var(--control);
    color: var(--ink-secondary);
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
}

.config-badge::before {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--ink-muted);
    content: "";
}

.config-badge__live {
    display: none;
}

.conversation-live .config-badge {
    background: var(--success-soft);
    color: var(--success);
}

.conversation-live .config-badge::before {
    background: var(--success);
    box-shadow: 0 0 0 3px rgb(22 115 75 / .12);
    animation: status-breathe 1.8s var(--ease-out) infinite;
}

.conversation-live .config-badge__idle {
    display: none;
}

.conversation-live .config-badge__live {
    display: inline;
}

.config-list {
    margin: 0;
}

.config-row {
    display: grid;
    grid-template-columns: 38px minmax(88px, .8fr) minmax(0, 1.35fr);
    align-items: center;
    gap: 10px;
    min-height: 72px;
    border-bottom: 1px solid var(--control);
}

.config-row:last-child {
    border-bottom: 0;
}

.config-row dt,
.config-row dd {
    margin: 0;
}

.config-row dt {
    color: var(--ink-secondary);
    font-size: 15px;
}

.config-row dd {
    overflow: hidden;
    color: var(--ink);
    font-size: 15px;
    font-weight: 650;
    text-align: right;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.config-icon {
    display: grid;
    width: 32px;
    height: 32px;
    place-items: center;
    border-radius: 8px;
    background: var(--control);
    color: var(--ink-secondary);
}

.config-icon::before {
    width: 18px;
    height: 18px;
    background: currentColor;
    content: "";
    -webkit-mask: var(--config-icon) center / contain no-repeat;
    mask: var(--config-icon) center / contain no-repeat;
}

.config-icon--mic { --config-icon: var(--icon-mic); }
.config-icon--model { --config-icon: var(--icon-message); }
.config-icon--voice { --config-icon: var(--icon-volume); }
.config-icon--motion { --config-icon: var(--icon-motion); }

.config-note {
    margin: 18px 0 0;
    padding-top: 18px;
    border-top: 1px solid var(--line);
    color: var(--ink-secondary);
    font-size: 15px;
    line-height: 1.6;
}

.identity-section + .identity-section {
    margin-top: 34px;
    padding-top: 32px;
    border-top: 1px solid var(--line);
}

#identity-main .form {
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}

.identity-section__head {
    margin-bottom: 20px;
}

.identity-section__head h3,
.identity-section__head p {
    margin: 0;
}

.identity-section__head h3 {
    color: var(--ink);
    font-size: 20px;
    font-weight: 650;
    line-height: 1.4;
}

.identity-section__head p {
    max-width: 70ch;
    margin-top: 5px;
    color: var(--ink-secondary);
    font-size: 16px;
    line-height: 1.6;
}

#profile-picker,
#new-profile-name,
#new-profile-instructions {
    margin: 0 0 18px !important;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}

#profile-picker label,
#new-profile-name label,
#new-profile-instructions label {
    color: var(--ink) !important;
    font-size: 15px !important;
    font-weight: 650 !important;
    letter-spacing: 0 !important;
}

#profile-picker label span,
#new-profile-name label span,
#new-profile-instructions label span,
#profile-picker .prose p {
    color: var(--ink-secondary) !important;
}

#profile-picker .wrap,
#new-profile-name .wrap,
#new-profile-instructions .wrap {
    border: 1px solid transparent !important;
    border-radius: 8px !important;
    background: var(--control) !important;
    box-shadow: none !important;
    transition: border-color 180ms var(--ease-out), background-color 180ms var(--ease-out),
                box-shadow 180ms var(--ease-out) !important;
}

#profile-picker .wrap:hover,
#new-profile-name .wrap:hover,
#new-profile-instructions .wrap:hover {
    border-color: var(--line-strong) !important;
}

#profile-picker .wrap:focus-within,
#new-profile-name .wrap:focus-within,
#new-profile-instructions .wrap:focus-within {
    border-color: var(--signal-deep) !important;
    background: var(--surface) !important;
    box-shadow: 0 0 0 3px rgb(228 155 15 / .24) !important;
}

#profile-picker input,
#new-profile-name input,
#new-profile-name textarea,
#new-profile-instructions textarea {
    border: 0 !important;
    background-color: transparent !important;
    color: var(--ink) !important;
    font-family: inherit !important;
    font-size: 17px !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
}

#profile-picker input,
#new-profile-name input,
#new-profile-name textarea {
    min-height: 50px !important;
}

#profile-picker input {
    padding-left: 46px !important;
    background-image: var(--icon-search) !important;
    background-position: 16px center !important;
    background-size: 20px 20px !important;
    background-repeat: no-repeat !important;
}

#new-profile-name input,
#new-profile-name textarea {
    padding: 0 16px !important;
    resize: none !important;
}

#new-profile-instructions textarea {
    min-height: 220px !important;
    padding: 14px 16px !important;
    line-height: 1.65 !important;
    resize: vertical !important;
}

#profile-picker input::placeholder,
#new-profile-name input::placeholder,
#new-profile-name textarea::placeholder,
#new-profile-instructions textarea::placeholder {
    color: var(--ink-secondary) !important;
    opacity: 1 !important;
}

#profile-picker .dropdown-arrow {
    color: var(--ink-secondary) !important;
}

.identity-action-row {
    align-items: center !important;
    gap: 12px !important;
}

.identity-action-row .command-button {
    min-width: 190px !important;
}

.identity-action-row #profile-status,
.identity-action-row #save-status {
    flex: 1 1 auto !important;
}

.settings-list {
    margin: 0;
    border-top: 1px solid var(--line);
}

.settings-row {
    display: grid;
    grid-template-columns: minmax(170px, .8fr) minmax(0, 1.4fr);
    gap: 28px;
    padding: 18px 0;
    border-bottom: 1px solid var(--control);
}

.settings-row dt,
.settings-row dd {
    margin: 0;
}

.settings-row dt {
    color: var(--ink-secondary);
    font-size: 15px;
}

.settings-row dd {
    color: var(--ink);
    font-size: 16px;
    font-weight: 600;
    text-align: right;
    overflow-wrap: anywhere;
}

.settings-row code {
    color: var(--ink);
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 14px;
}

.settings-state {
    display: inline-flex;
    align-items: center;
    gap: 7px;
}

.settings-state::before {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--success);
    content: "";
}

.settings-state--off::before {
    background: var(--ink-muted);
}

.settings-help {
    margin: 22px 0 0;
    color: var(--ink-secondary);
    font-size: 15px;
    line-height: 1.6;
}

.pipeline {
    display: flex;
    align-items: stretch;
    margin-top: 6px;
    overflow-x: auto;
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    scrollbar-width: thin;
}

.pipeline-step {
    position: relative;
    display: grid;
    min-width: 170px;
    flex: 1 0 170px;
    align-content: center;
    gap: 4px;
    min-height: 118px;
    padding: 18px 28px 18px 18px;
    border-right: 1px solid var(--control);
}

.pipeline-step:last-child {
    border-right: 0;
}

.pipeline-step::after {
    position: absolute;
    top: 50%;
    right: -5px;
    z-index: 1;
    width: 8px;
    height: 8px;
    border-top: 1px solid var(--line-strong);
    border-right: 1px solid var(--line-strong);
    background: var(--surface);
    content: "";
    transform: translateY(-50%) rotate(45deg);
}

.pipeline-step:last-child::after {
    display: none;
}

.pipeline-step span,
.pipeline-step strong {
    letter-spacing: 0;
}

.pipeline-step span {
    color: var(--ink-secondary);
    font-size: 14px;
}

.pipeline-step strong {
    color: var(--ink);
    font-size: 17px;
    font-weight: 650;
}

.about-copy {
    max-width: 72ch;
    margin: 24px 0 0;
    color: var(--ink-secondary);
    font-size: 17px;
    line-height: 1.7;
}

.about-capabilities {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 20px;
    margin: 20px 0 0;
    padding: 20px 0 0;
    border-top: 1px solid var(--line);
}

.about-capabilities span {
    position: relative;
    padding-left: 16px;
    color: var(--ink);
    font-size: 15px;
    font-weight: 600;
}

.about-capabilities span::before {
    position: absolute;
    top: .58em;
    left: 0;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--signal);
    content: "";
}

.gradio-container footer {
    display: none !important;
}

@keyframes status-breathe {
    50% { box-shadow: 0 0 0 6px rgb(22 115 75 / .05); }
}

@media (prefers-reduced-motion: reduce) {
    #main-tabs [role="tab"],
    #main-tabs [role="tab"]::after,
    .command-button,
    #profile-picker .wrap,
    #new-profile-name .wrap,
    #new-profile-instructions .wrap {
        transition: none !important;
    }

    .conversation-live .config-badge::before {
        animation: none !important;
    }
}

@media (max-width: 960px) {
    #conversation-layout {
        flex-direction: column !important;
    }

    #conversation-main,
    #session-side {
        width: 100% !important;
        flex: 1 1 auto !important;
    }

    .config-list {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0 20px;
    }
}

@media (max-width: 640px) {
    .device-bar {
        min-height: 86px;
    }

    .device-brand__mark {
        width: 38px;
        height: 38px;
        flex-basis: 38px;
    }

    .device-brand__title {
        font-size: 19px;
    }

    .device-state__copy {
        display: none;
    }

    #main-tabs {
        margin-top: 14px !important;
    }

    #main-tabs [role="tablist"] {
        gap: 20px !important;
        margin-bottom: 20px !important;
    }

    .page-intro {
        margin-bottom: 18px;
    }

    .page-intro h2 {
        font-size: 26px;
    }

    #conversation-main,
    #identity-main,
    #settings-main,
    #about-main,
    #session-side {
        padding: 20px !important;
    }

    #control-actions,
    .identity-action-row {
        flex-direction: column !important;
    }

    #control-actions .command-button,
    .identity-action-row .command-button,
    .identity-action-row #profile-status,
    .identity-action-row #save-status {
        width: 100% !important;
        min-width: 0 !important;
    }

    #transcript {
        min-height: 440px !important;
    }

    .config-list {
        display: block;
    }

    .settings-row {
        grid-template-columns: 1fr;
        gap: 5px;
    }

    .settings-row dd {
        text-align: left;
    }
}
"""


def launch_gradio(
    gateway_url: str = "ws://localhost:18789",
    robot_name: str | None = None,
    robot_host: str | None = None,
    robot_port: int | None = None,
    enable_camera: bool = True,
    enable_openclaw: bool = True,
    share: bool = False,
) -> None:
    """启动心宠网页控制台。"""
    from reachy_mini_openclaw.config import config, set_custom_profile
    from reachy_mini_openclaw.prompts import get_available_profiles, save_custom_profile

    app_instance = None

    def start_conversation() -> str:
        nonlocal app_instance
        from reachy_mini_openclaw.main import ClawBodyCore

        if app_instance is not None:
            return "对话已经在运行"

        try:
            app_instance = ClawBodyCore(
                gateway_url=gateway_url,
                robot_name=robot_name,
                robot_host=robot_host,
                robot_port=robot_port,
                enable_camera=enable_camera,
                enable_openclaw=enable_openclaw,
            )

            def run_app() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(app_instance.run())
                except Exception as exc:
                    logger.error("App error: %s", exc)
                finally:
                    loop.close()

            threading.Thread(target=run_app, daemon=True).start()
            return "对话已启动，正在等待语音输入"
        except Exception as exc:
            return f"启动失败：{exc}"

    def stop_conversation() -> str:
        nonlocal app_instance

        if app_instance is None:
            return "对话当前未运行"

        try:
            app_instance.stop()
            app_instance = None
            return "对话已停止"
        except Exception as exc:
            return f"停止失败：{exc}"

    def apply_profile(profile_name: str) -> str:
        set_custom_profile(profile_name if profile_name else None)
        return f"已应用身份配置：{profile_name or '默认配置'}"

    def save_profile(name: str, instructions: str) -> str:
        if save_custom_profile(name, instructions):
            return f"身份配置已保存：{name}"
        return "身份配置保存失败"

    model_name = escape(str(config.MINIMAX_MODEL))
    robot_address = escape(f"{robot_host or config.ROBOT_HOST}:{robot_port or config.ROBOT_PORT}")
    gateway_address = escape(str(gateway_url))
    asr_language = escape(str(config.BAIDU_ASR_LANGUAGE))
    tts_voice = escape(str(config.BAIDU_TTS_PER))
    llm_key_state = "已配置" if bool(getattr(config, "MINIMAX_API_KEY", "")) else "未配置"
    baidu_key_state = (
        "已配置"
        if bool(getattr(config, "BAIDU_API_KEY", "")) and bool(getattr(config, "BAIDU_SECRET_KEY", ""))
        else "未配置"
    )
    logo_path = Path(__file__).with_name("assets") / "xinchong-logo.jpg"
    logo_data_uri = "data:image/jpeg;base64," + base64.b64encode(logo_path.read_bytes()).decode("ascii")

    with gr.Blocks(
        title="心宠对话控制台",
        theme=gr.themes.Base(),
        css=UI_CSS,
        elem_id="app-shell",
    ) as demo:
        gr.HTML(
            f"""
            <header class="device-bar">
              <div class="device-brand">
                <span class="device-brand__mark">
                  <img src="{logo_data_uri}" alt="心宠 Logo">
                </span>
                <div>
                  <p class="device-brand__name">心宠</p>
                  <h1 class="device-brand__title">对话控制台</h1>
                </div>
              </div>
              <div class="device-state" aria-label="控制服务已加载">
                <span class="device-state__dot" aria-hidden="true"></span>
                <div class="device-state__copy">
                  <p class="device-state__primary">控制服务已加载</p>
                  <p class="device-state__secondary">本地设备</p>
                </div>
              </div>
            </header>
            """,
            elem_id="topbar",
        )

        with gr.Tabs(elem_id="main-tabs"):
            with gr.Tab("对话"):
                gr.HTML(
                    """
                    <section class="page-intro">
                      <h2>语音对话</h2>
                      <p>启动会话后，直接对着麦克风说话。机器人会听取、理解，并用声音和动作回应。</p>
                    </section>
                    """
                )

                with gr.Row(elem_id="conversation-layout"):
                    with gr.Column(scale=8, elem_id="conversation-main"):
                        gr.HTML(
                            """
                            <div class="section-heading">
                              <div>
                                <h3>当前会话</h3>
                                <p>对话记录会在识别完成后自动出现</p>
                              </div>
                            </div>
                            """
                        )
                        with gr.Row(elem_id="control-actions"):
                            start_btn = gr.Button(
                                "开始对话",
                                variant="primary",
                                scale=2,
                                elem_id="start-conversation",
                                elem_classes=["command-button"],
                            )
                            stop_btn = gr.Button(
                                "停止",
                                variant="secondary",
                                scale=1,
                                elem_id="stop-conversation",
                                elem_classes=["command-button"],
                            )

                        status_output = gr.Markdown("准备开始对话", elem_id="conversation-status")
                        transcript = gr.Chatbot(
                            show_label=False,
                            height=520,
                            type="messages",
                            elem_id="transcript",
                            placeholder="<strong>还没有对话</strong><br>点击“开始对话”，然后自然说话即可。",
                        )

                    with gr.Column(scale=4, elem_id="session-side"):
                        gr.HTML(
                            f"""
                            <section class="config-panel">
                              <div class="config-panel__head">
                                <div>
                                  <h3>会话配置</h3>
                                  <p>当前语音处理链路</p>
                                </div>
                                <span class="config-badge">
                                  <span class="config-badge__idle">待机</span>
                                  <span class="config-badge__live">运行中</span>
                                </span>
                              </div>
                              <dl class="config-list">
                                <div class="config-row">
                                  <span class="config-icon config-icon--mic" aria-hidden="true"></span>
                                  <dt>语音输入</dt>
                                  <dd>百度语音识别</dd>
                                </div>
                                <div class="config-row">
                                  <span class="config-icon config-icon--model" aria-hidden="true"></span>
                                  <dt>对话模型</dt>
                                  <dd title="{model_name}">{model_name}</dd>
                                </div>
                                <div class="config-row">
                                  <span class="config-icon config-icon--voice" aria-hidden="true"></span>
                                  <dt>语音输出</dt>
                                  <dd>百度语音合成</dd>
                                </div>
                                <div class="config-row">
                                  <span class="config-icon config-icon--motion" aria-hidden="true"></span>
                                  <dt>动作表达</dt>
                                  <dd>自动动作</dd>
                                </div>
                              </dl>
                              <p class="config-note">服务启动后，保持机器人控制软件和机器人电源处于连接状态。</p>
                            </section>
                            """
                        )

                def get_transcript() -> list[dict]:
                    if app_instance is None or not hasattr(app_instance, "handler"):
                        return []
                    return list(app_instance.handler.display_history)

                start_btn.click(
                    start_conversation,
                    outputs=[status_output],
                    js="() => document.documentElement.classList.add('conversation-live')",
                )
                stop_btn.click(
                    stop_conversation,
                    outputs=[status_output],
                    js="() => document.documentElement.classList.remove('conversation-live')",
                )
                gr.Timer(value=1.0).tick(get_transcript, outputs=[transcript])

            with gr.Tab("身份与语气"):
                gr.HTML(
                    """
                    <section class="page-intro">
                      <h2>身份与语气</h2>
                      <p>决定心宠如何认识自己、记住长期信息，以及怎样与你说话。</p>
                    </section>
                    """
                )

                with gr.Column(elem_id="identity-main"):
                    gr.HTML(
                        """
                        <section class="identity-section">
                          <div class="identity-section__head">
                            <h3>当前身份</h3>
                            <p>选择已经保存的身份配置，并立即应用到之后的回答。</p>
                          </div>
                        </section>
                        """
                    )
                    profiles = get_available_profiles()
                    profile_dropdown = gr.Dropdown(
                        choices=[""] + profiles,
                        value="",
                        label="选择身份配置",
                        info="可以输入名称搜索已有配置",
                        elem_id="profile-picker",
                    )
                    with gr.Row(elem_classes=["identity-action-row"]):
                        apply_btn = gr.Button(
                            "应用身份配置",
                            variant="primary",
                            elem_id="apply-profile",
                            elem_classes=["command-button"],
                        )
                        profile_status = gr.Markdown("选择一个身份配置后应用", elem_id="profile-status")

                    gr.HTML(
                        """
                        <section class="identity-section">
                          <div class="identity-section__head">
                            <h3>创建新的身份</h3>
                            <p>写清名字、性格、记忆和表达偏好。保存后可在上方随时切换。</p>
                          </div>
                        </section>
                        """
                    )
                    new_name = gr.Textbox(
                        label="配置名称",
                        placeholder="例如：小芯 · 专家助手",
                        elem_id="new-profile-name",
                    )
                    new_instructions = gr.Textbox(
                        label="身份与语气说明",
                        lines=10,
                        placeholder="填写名字、性格、长期记忆、回答习惯和需要遵守的规则……",
                        elem_id="new-profile-instructions",
                    )
                    with gr.Row(elem_classes=["identity-action-row"]):
                        save_btn = gr.Button(
                            "保存身份配置",
                            variant="primary",
                            elem_id="save-profile",
                            elem_classes=["command-button"],
                        )
                        save_status = gr.Markdown("填写完成后保存", elem_id="save-status")

                    apply_btn.click(apply_profile, inputs=[profile_dropdown], outputs=[profile_status])
                    save_btn.click(save_profile, inputs=[new_name, new_instructions], outputs=[save_status])

            with gr.Tab("设置"):
                gr.HTML(
                    """
                    <section class="page-intro">
                      <h2>运行设置</h2>
                      <p>查看当前机器人、模型和语音服务配置。密钥只显示配置状态，不在网页中明文回显。</p>
                    </section>
                    """
                )

                with gr.Column(elem_id="settings-main"):
                    gr.HTML(
                        f"""
                        <div class="section-heading">
                          <div>
                            <h3>当前配置</h3>
                            <p>修改项目根目录的 .env 后，重启服务即可更新</p>
                          </div>
                        </div>
                        <dl class="settings-list">
                          <div class="settings-row">
                            <dt>机器人地址</dt>
                            <dd><code>{robot_address}</code></dd>
                          </div>
                          <div class="settings-row">
                            <dt>OpenClaw 网关</dt>
                            <dd><code>{gateway_address}</code></dd>
                          </div>
                          <div class="settings-row">
                            <dt>对话模型</dt>
                            <dd><code>{model_name}</code></dd>
                          </div>
                          <div class="settings-row">
                            <dt>阿里云模型密钥</dt>
                            <dd><span class="settings-state{' settings-state--off' if llm_key_state == '未配置' else ''}">{llm_key_state}</span></dd>
                          </div>
                          <div class="settings-row">
                            <dt>百度语音密钥</dt>
                            <dd><span class="settings-state{' settings-state--off' if baidu_key_state == '未配置' else ''}">{baidu_key_state}</span></dd>
                          </div>
                          <div class="settings-row">
                            <dt>语音识别语言</dt>
                            <dd>{asr_language}</dd>
                          </div>
                          <div class="settings-row">
                            <dt>语音音色</dt>
                            <dd><code>{tts_voice}</code></dd>
                          </div>
                          <div class="settings-row">
                            <dt>摄像头</dt>
                            <dd><span class="settings-state{' settings-state--off' if not enable_camera else ''}">{'已启用' if enable_camera else '未启用'}</span></dd>
                          </div>
                          <div class="settings-row">
                            <dt>OpenClaw</dt>
                            <dd><span class="settings-state{' settings-state--off' if not enable_openclaw else ''}">{'已启用' if enable_openclaw else '未启用'}</span></dd>
                          </div>
                        </dl>
                        <p class="settings-help">配置文件不会被打包进 Docker 镜像。正式服务与 7861 预览服务都会读取本机的 .env。</p>
                        """
                    )

            with gr.Tab("关于"):
                gr.HTML(
                    """
                    <section class="page-intro">
                      <h2>关于心宠</h2>
                      <p>这个项目把语音识别、对话模型、语音合成与机器人动作连接成一条完整链路。</p>
                    </section>
                    """
                )

                with gr.Column(elem_id="about-main"):
                    gr.HTML(
                        """
                        <div class="section-heading">
                          <div>
                            <h3>一次回答如何产生</h3>
                            <p>从你的声音到机器人的声音与动作</p>
                          </div>
                        </div>
                        <div class="pipeline" aria-label="语音对话处理流程">
                          <div class="pipeline-step"><span>输入</span><strong>你的声音</strong></div>
                          <div class="pipeline-step"><span>识别</span><strong>百度 ASR</strong></div>
                          <div class="pipeline-step"><span>理解</span><strong>Qwen</strong></div>
                          <div class="pipeline-step"><span>合成</span><strong>百度 TTS</strong></div>
                          <div class="pipeline-step"><span>表达</span><strong>声音与动作</strong></div>
                        </div>
                        <p class="about-copy">心宠会持续监听麦克风，在检测到一句完整语音后进行识别和回答。身份配置决定它如何介绍自己、保留哪些长期信息，以及采用怎样的表达方式。</p>
                        <div class="about-capabilities" aria-label="当前能力">
                          <span>中文语音对话</span>
                          <span>自动动作表达</span>
                          <span>可定制身份与记忆</span>
                          <span>摄像头与人脸跟踪</span>
                        </div>
                        """
                    )

    demo.launch(share=share, server_name="0.0.0.0", server_port=7860)
