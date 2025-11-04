import { Newspaper, Sparkles, LogIn } from 'lucide-react';
import { SiTelegram } from 'react-icons/si';
import { useLocation } from 'wouter';
import DiamondBackground from './DiamondBackground';
import BenefitCard from './BenefitCard';
import FloatingEmojis from './FloatingEmojis';

export default function ComingSoon() {
  const [, setLocation] = useLocation();
  
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
          <div className="max-w-7xl mx-auto">
            <h1 
              className="text-3xl md:text-4xl font-black tracking-wider text-center"
              style={{
                background: 'linear-gradient(135deg, #84cc16 0%, #22c55e 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                filter: 'drop-shadow(0 0 20px rgba(132, 204, 22, 0.3))',
                fontFamily: 'Montserrat, sans-serif',
                letterSpacing: '0.1em',
              }}
              data-testid="text-logo"
            >
              WIRALIS
            </h1>
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
                title="Красивые новостные посты"
                description="Современный дизайн и удобный формат для ваших новостей"
                delay={600}
              />
              <BenefitCard
                icon={LogIn}
                title="Жду Сайт"
                description="Войдите через код из бота и получите доступ к вашему профилю"
                delay={700}
                onClick={() => setLocation('/register')}
              />
              <BenefitCard
                icon={Sparkles}
                title="И многое другое"
                description="Ещё больше возможностей появится совсем скоро"
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
            <p className="text-center text-white/60 text-sm px-4" data-testid="text-copyright">
              WIRALIS – Все права защищены
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
