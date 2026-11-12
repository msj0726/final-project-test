// 프로토타입의 인라인 SVG. 정적 문자열이므로 v-html 로 안전하게 사용합니다.
const stroke = (p: string, size = 30) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="var(--pri)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`

export const IC = {
  logo: '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="7" width="2.6" height="6" rx="1.3" fill="#fff"/><rect x="7.7" y="3" width="2.6" height="12" rx="1.3" fill="#fff"/><rect x="13.4" y="5.5" width="2.6" height="7" rx="1.3" fill="#fff"/></svg>',
  play: '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4l13 8-13 8z" fill="#fff"/></svg>',
  playMini: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 1l9 5-9 5z" fill="currentColor"/></svg>',
  pauseMini: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 1h3v10H2zM7 1h3v10H7z" fill="currentColor"/></svg>',
  cam: stroke('<rect x="3" y="6" width="12" height="12" rx="3"/><path d="M15 10l6-3v10l-6-3"/>', 24),
  chart: stroke('<path d="M4 19V5M4 19h16M8 15l4-4 3 3 5-6"/>'),
  folder: stroke('<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>'),
  cal: stroke('<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M8 3v4M16 3v4M3 10h18"/>'),
  shield: stroke('<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>'),
  check: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10"/></svg>',
}
