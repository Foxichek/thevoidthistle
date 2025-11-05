import { Newspaper, Sparkles, LogIn, HelpCircle, User } from 'lucide-react';
import { SiTelegram } from 'react-icons/si';
import { useLocation } from 'wouter';
import { useState, useEffect } from 'react';
import DiamondBackground from './DiamondBackground';
import BenefitCard from './BenefitCard';
import FloatingEmojis from './FloatingEmojis';

interface WiralisUser {
  id: string;
  telegramId: number;
  nickname: string;
}

export default function ComingSoon() {
  const [, setLocation] = useLocation();
  const [showHowModal, setShowHowModal] = useState(false);
  const [loggedInUser, setLoggedInUser] = useState<WiralisUser | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('wiralis_user');
    if (saved) {
      try {
        setLoggedInUser(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse saved user', e);
      }
    }
  }, []);
  
  return (
    <div className="min-h-screen relative overflow-hidden bg-gradient-to-br from-purple-900 via-purple-800 to-purple-900">
      <div 
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage: `repeating-linear-gradient(
            -45deg,
            transparent,
            transparent 35px,
            rgba(139, 92, 246, 0.1) 35px,
            rgba(139, 92, 246, 0.1) 70px
          )`,
          animation: 'gradient-shift 15s ease infinite',
        }}
      />

      <DiamondBackground />
      <FloatingEmojis />

      <div className="relative z-10 flex flex-col min-h-screen">
        <header className="py-8 px-8 animate-fade-in" style={{ animationDelay: '100ms' }}>
          <div className={`max-w-7xl mx-auto flex items-center ${loggedInUser ? 'justify-between' : 'justify-center'}`}>
            <h1 
              className="text-3xl md:text-4xl font-black tracking-wider cursor-pointer"
              style={{
                background: 'linear-gradient(135deg, #84cc16 0%, #22c55e 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                filter: 'drop-shadow(0 0 20px rgba(132, 204, 22, 0.3))',
                fontFamily: 'Montserrat, sans-serif',
                letterSpacing: '0.1em',
              }}
              onClick={() => setLocation('/')}
              data-testid="text-logo"
            >
              WIRALIS
            </h1>
            {loggedInUser && (
              <button
                onClick={() => setLocation(`/profile/${loggedInUser.id}`)}
                className="flex items-center gap-2 px-4 py-2 backdrop-blur-xl border border-white/30 rounded-lg text-white hover-elevate transition-all duration-300"
                style={{
                  background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.12) 0%, rgba(255, 255, 255, 0.08) 100%)',
                  boxShadow: '0 4px 16px rgba(139, 92, 246, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.15)',
                }}
                data-testid="button-profile"
              >
                <User className="w-5 h-5" />
                <span className="hidden sm:inline">Мой профиль</span>
              </button>
            )}
          </div>
        </header>

        <main className="flex-1 flex items-center justify-center px-6 md:px-8 py-12">
          <div className="max-w-5xl w-full space-y-12 md:space-y-16">
            <div className="text-center space-y-4 md:space-y-6 animate-fade-in" style={{ animationDelay: '300ms' }}>
              <h2 
                className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-black text-white tracking-tight px-4"
                data-testid="text-main-heading"
              >
                В РАЗРАБОТКЕ
              </h2>
              <p 
                className="text-lg sm:text-xl md:text-2xl text-white/90 px-4"
                data-testid="text-subheading"
              >
                Мы ещё строим сайт
              </p>
            </div>

            <div 
              className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 md:gap-8 px-4 animate-fade-in"
              style={{ animationDelay: '500ms' }}
            >
              <BenefitCard
                icon={Newspaper}
                title="Новости и Анонсы"
                description="Будут публиковаться новости и анонсы обновлений платформы"
                delay={600}
              />
              <BenefitCard
                icon={loggedInUser ? User : LogIn}
                title="Жду Сайт"
                description={loggedInUser ? `Вы уже с нами, ${loggedInUser.nickname}! Ждём выхода полной версии` : "Войдите через код из бота и получите доступ к вашему профилю"}
                delay={700}
                onClick={loggedInUser ? () => setLocation(`/profile/${loggedInUser.id}`) : () => setLocation('/register')}
                onSecondaryClick={!loggedInUser ? () => setShowHowModal(true) : undefined}
                secondaryIcon={!loggedInUser ? HelpCircle : undefined}
                secondaryTooltip={!loggedInUser ? "Как это работает?" : undefined}
              />
              <BenefitCard
                icon={Sparkles}
                title="И многое другое"
                description="Профили дня, тренды, социальные возможности - все это скоро появится вне бота WIRALIS"
                delay={800}
              />
            </div>
          </div>
        </main>

        <footer className="py-6 md:py-8 px-6 md:px-8 animate-fade-in" style={{ animationDelay: '900ms' }}>
          <div className="max-w-7xl mx-auto space-y-4 md:space-y-6">
            <div className="flex flex-col sm:flex-row flex-wrap justify-center items-center gap-3 md:gap-4">
              <a
                href="https://t.me/WIRALISCHANNEL"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 backdrop-blur-xl border border-white/30 rounded-lg text-white hover-elevate transition-all duration-300"
                style={{
                  background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.12) 0%, rgba(255, 255, 255, 0.08) 100%)',
                  boxShadow: '0 4px 16px rgba(139, 92, 246, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.15)',
                }}
                data-testid="link-telegram-channel"
              >
                <SiTelegram className="w-5 h-5" />
                <span className="font-medium">Telegram-канал</span>
              </a>
              <a
                href="https://t.me/wiralis_bot"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 backdrop-blur-xl border border-white/30 rounded-lg text-white hover-elevate transition-all duration-300"
                style={{
                  background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.12) 0%, rgba(255, 255, 255, 0.08) 100%)',
                  boxShadow: '0 4px 16px rgba(139, 92, 246, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.15)',
                }}
                data-testid="link-telegram-bot"
              >
                <SiTelegram className="w-5 h-5" />
                <span className="font-medium">Telegram-бот</span>
              </a>
            </div>
            <p className="text-center text-white/50 text-xs px-4">
              🎉 Публичная версия выйдет в декабре 2025 или в начале 2026 года
            </p>
            <p className="text-center text-white/60 text-sm px-4" data-testid="text-copyright">
              © 2025 WIRALIS Team – Все права защищены
            </p>
          </div>
        </footer>
      </div>

      {/* Модальное окно "Как это работает?" */}
      {showHowModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
          onClick={() => setShowHowModal(false)}
          style={{
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(8px)',
          }}
        >
          <div 
            className="max-w-2xl w-full backdrop-blur-xl border border-white/30 rounded-2xl p-8 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.25) 0%, rgba(139, 92, 246, 0.15) 100%)',
              boxShadow: '0 20px 60px rgba(139, 92, 246, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2)',
            }}
          >
            <div className="flex justify-between items-start mb-6">
              <h3 className="text-2xl md:text-3xl font-bold text-white">
                🤔 Как это работает?
              </h3>
              <button
                onClick={() => setShowHowModal(false)}
                className="text-white/70 hover:text-white transition-colors text-2xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="space-y-6 text-white/90">
              <div className="space-y-4">
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center text-green-400 font-bold">
                    1
                  </div>
                  <div>
                    <h4 className="font-semibold text-white mb-1">Откройте Telegram-бот</h4>
                    <p className="text-sm text-white/80">
                      Перейдите в <a href="https://t.me/wiralis_bot" target="_blank" rel="noopener noreferrer" className="text-green-400 hover:text-green-300 underline">@wiralis_bot</a> и отправьте команду <code className="px-2 py-1 bg-white/10 rounded">/web</code>
                    </p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center text-green-400 font-bold">
                    2
                  </div>
                  <div>
                    <h4 className="font-semibold text-white mb-1">Получите код доступа</h4>
                    <p className="text-sm text-white/80">
                      Бот сгенерирует уникальный 6-значный код, который действителен 10 минут
                    </p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center text-green-400 font-bold">
                    3
                  </div>
                  <div>
                    <h4 className="font-semibold text-white mb-1">Введите код на сайте</h4>
                    <p className="text-sm text-white/80">
                      Нажмите кнопку "Жду Сайт" и введите полученный код
                    </p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-500/20 border border-green-500/50 flex items-center justify-center text-green-400 font-bold">
                    4
                  </div>
                  <div>
                    <h4 className="font-semibold text-white mb-1">Готово!</h4>
                    <p className="text-sm text-white/80">
                      Получите доступ к вашему профилю и всем возможностям платформы
                    </p>
                  </div>
                </div>
              </div>

              <div 
                className="mt-6 p-4 rounded-xl border border-purple-400/30"
                style={{
                  background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%)',
                }}
              >
                <p className="text-sm text-white/90">
                  💡 <strong>Подсказка:</strong> Код можно использовать только один раз. Если он истек, просто запросите новый командой <code className="px-2 py-1 bg-white/10 rounded">/web</code>
                </p>
              </div>
            </div>

            <div className="mt-8 flex justify-center">
              <button
                onClick={() => setShowHowModal(false)}
                className="px-8 py-3 backdrop-blur-xl border border-white/30 rounded-lg text-white font-medium hover-elevate transition-all duration-300"
                style={{
                  background: 'linear-gradient(135deg, rgba(132, 204, 22, 0.25) 0%, rgba(34, 197, 94, 0.25) 100%)',
                  boxShadow: '0 4px 16px rgba(132, 204, 22, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.15)',
                }}
              >
                Понятно
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
