import React from "react";

interface CourseCoverSvgProps {
  courseId: string;
  title: string;
  className?: string;
}

/**
 * Единая редакционная серия обложек курсов LITHOS («Геологический атлас»).
 * Один ясный научный образ на обложку (разрез, кривая или модель) без перегруженных формул и битых изображений.
 */
export const CourseCoverSvg: React.FC<CourseCoverSvgProps> = ({ courseId, title, className = "" }) => {
  const id = courseId.toLowerCase();

  if (id.includes("latyshova")) {
    // Разрез ствола скважины и две каротажные кривые
    return (
      <svg viewBox="0 0 480 240" className={className} role="img" aria-label={`Обложка курса: ${title}`}>
        <rect width="480" height="240" fill="#131720" />
        <rect x="0" y="138" width="480" height="102" fill="#0B1926" />
        <line x1="0" y1="138" x2="480" y2="138" stroke="#F43F5E" strokeWidth="2" strokeDasharray="6 4" />
        <rect x="218" y="0" width="44" height="240" fill="#1B212E" />
        <rect x="234" y="54" width="12" height="58" rx="4" fill="#D97736" />
        <path d="M56 12 L56 60 L132 68 L132 132 L68 144 L68 228" fill="none" stroke="#38BDF8" strokeWidth="3" />
        <path d="M320 12 L320 56 L418 64 L418 134 L336 146 L336 228" fill="none" stroke="#10B981" strokeWidth="3" />
        <path d="M342 12 L342 56 L386 66 L386 134 L350 146 L350 228" fill="none" stroke="#F59E0B" strokeWidth="2" strokeDasharray="5 4" />
        <text x="20" y="222" fill="#A39E93" fontSize="12" fontFamily="Inter, sans-serif">Схема разреза · ВНК и кривые ГИС</text>
      </svg>
    );
  }

  if (id.includes("basniev")) {
    // Логарифмическая воронка депрессии
    return (
      <svg viewBox="0 0 480 240" className={className} role="img" aria-label={`Обложка курса: ${title}`}>
        <rect width="480" height="240" fill="#131720" />
        <ellipse cx="240" cy="64" rx="190" ry="30" fill="none" stroke="#38BDF8" strokeWidth="1.5" strokeOpacity="0.45" />
        <ellipse cx="240" cy="64" rx="125" ry="20" fill="none" stroke="#10B981" strokeWidth="1.5" strokeDasharray="5 4" strokeOpacity="0.7" />
        <path d="M50 64 Q212 72 232 208 L248 208 Q268 72 430 64" fill="#D97736" fillOpacity="0.16" stroke="#F59E0B" strokeWidth="2.8" />
        <rect x="234" y="42" width="12" height="176" rx="3" fill="#F4F1EA" fillOpacity="0.85" />
        <text x="20" y="222" fill="#A39E93" fontSize="12" fontFamily="Inter, sans-serif">Схема · Воронка давления и приток</text>
      </svg>
    );
  }

  if (id.includes("kuznetsov")) {
    // Карбонатная рифовая постройка
    return (
      <svg viewBox="0 0 480 240" className={className} role="img" aria-label={`Обложка курса: ${title}`}>
        <rect width="480" height="240" fill="#131720" />
        <line x1="0" y1="46" x2="480" y2="46" stroke="#38BDF8" strokeWidth="1.5" strokeOpacity="0.5" />
        <path d="M0 192 Q120 190 164 118 Q240 48 316 118 Q360 190 480 192 L480 240 L0 240 Z" fill="#1E2532" stroke="#D97736" strokeWidth="2.5" />
        <path d="M168 192 Q240 88 312 192 Z" fill="#10B981" fillOpacity="0.22" stroke="#10B981" strokeWidth="1.8" />
        <text x="20" y="222" fill="#A39E93" fontSize="12" fontFamily="Inter, sans-serif">Схема · Фации карбонатного рифа</text>
      </svg>
    );
  }

  if (id.includes("baraboshkin")) {
    // Дельтовые рукава и конусы выноса
    return (
      <svg viewBox="0 0 480 240" className={className} role="img" aria-label={`Обложка курса: ${title}`}>
        <rect width="480" height="240" fill="#131720" />
        <path d="M0 170 Q170 150 280 95 Q380 48 480 45 L480 240 L0 240 Z" fill="#182330" />
        <path d="M40 120 C140 120 185 88 260 66 M40 120 C150 125 215 128 318 118 M40 120 C135 135 190 165 288 176" fill="none" stroke="#D97736" strokeWidth="3.2" strokeLinecap="round" />
        <text x="20" y="222" fill="#A39E93" fontSize="12" fontFamily="Inter, sans-serif">Схема · Дельтовые фации и русла</text>
      </svg>
    );
  }

  if (id.includes("barenblatt")) {
    // Волна возмущения давления во времени
    return (
      <svg viewBox="0 0 480 240" className={className} role="img" aria-label={`Обложка курса: ${title}`}>
        <rect width="480" height="240" fill="#131720" />
        <path d="M44 190 Q95 72 220 62 L440 62" fill="none" stroke="#38BDF8" strokeWidth="2.5" />
        <path d="M44 190 Q150 96 310 64 L440 62" fill="none" stroke="#10B981" strokeWidth="2.5" strokeDasharray="6 4" />
        <path d="M44 190 Q220 120 410 68 L440 62" fill="none" stroke="#D97736" strokeWidth="2.5" />
        <text x="20" y="222" fill="#A39E93" fontSize="12" fontFamily="Inter, sans-serif">Схема · Нестационарная фильтрация</text>
      </svg>
    );
  }

  if (id.includes("vendelshtein")) {
    // Повторные замеры и границы коллектора
    return (
      <svg viewBox="0 0 480 240" className={className} role="img" aria-label={`Обложка курса: ${title}`}>
        <rect width="480" height="240" fill="#131720" />
        <line x1="60" y1="190" x2="420" y2="54" stroke="#38BDF8" strokeWidth="2.5" />
        <line x1="60" y1="168" x2="420" y2="32" stroke="#F59E0B" strokeWidth="1.5" strokeDasharray="5 4" />
        <line x1="60" y1="212" x2="420" y2="76" stroke="#F59E0B" strokeWidth="1.5" strokeDasharray="5 4" />
        <circle cx="160" cy="148" r="5" fill="#10B981" />
        <circle cx="240" cy="118" r="5" fill="#10B981" />
        <circle cx="315" cy="96" r="5" fill="#10B981" />
        <circle cx="285" cy="154" r="6" fill="#F43F5E" />
        <text x="20" y="222" fill="#A39E93" fontSize="12" fontFamily="Inter, sans-serif">Схема · Критерии выделения коллекторов</text>
      </svg>
    );
  }

  // Пользовательская загруженная книга — универсальный геологический пласт
  return (
    <svg viewBox="0 0 480 240" className={className} role="img" aria-label={`Обложка курса: ${title}`}>
      <rect width="480" height="240" fill="#131720" />
      <path d="M0 112 Q160 88 320 116 T480 102 L480 240 L0 240 Z" fill="#1B212E" />
      <path d="M0 156 Q180 134 340 162 T480 148 L480 240 L0 240 Z" fill="#232A38" />
      <path d="M0 112 Q160 88 320 116 T480 102" fill="none" stroke="#D97736" strokeWidth="2.6" />
      <text x="20" y="222" fill="#A39E93" fontSize="12" fontFamily="Inter, sans-serif">Курс из вашей книги</text>
    </svg>
  );
};
