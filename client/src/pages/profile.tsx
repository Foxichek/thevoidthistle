import { useEffect, useState } from 'react';
import { useRoute, useLocation } from 'wouter';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { User, LogOut, Quote } from 'lucide-react';
import DiamondBackground from '@/components/DiamondBackground';
import FloatingEmojis from '@/components/FloatingEmojis';
import { SiTelegram } from 'react-icons/si';

interface WiralisUser {
  id: string;
  telegramId: number;
  nickname: string;
  username?: string | null;
  quote?: string | null;
  botId?: string | null;
  registeredAt: string;
}

export default function Profile() {
  const [, params] = useRoute('/profile/:userId');
  const [, setLocation] = useLocation();
  const [localUser, setLocalUser] = useState<WiralisUser | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('wiralis_user');
    if (saved) {
      try {
        setLocalUser(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse saved user', e);
      }
    }
  }, []);

  const { data: user, isLoading, error } = useQuery<WiralisUser>({
    queryKey: ['/api/profile', params?.userId],
    enabled: !!params?.userId,
  });

  const handleLogout = () => {
    localStorage.removeItem('wiralis_user');
    setLocation('/');
  };

  const displayUser = user || localUser;

  if (!params?.userId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-900 via-purple-800 to-purple-900">
        <p className="text-white">Пользователь не найден</p>
      </div>
    );
  }

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
          <div className="max-w-7xl mx-auto flex justify-between items-center">
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
              data-testid="link-logo"
            >
              WIRALIS
            </h1>
            <Button
              onClick={handleLogout}
              variant="outline"
              className="bg-white/10 border-white/20 text-white hover:bg-white/20"
              data-testid="button-logout"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Выйти
            </Button>
          </div>
        </header>

        <main className="flex-1 flex items-center justify-center px-6 md:px-8 py-12">
          <div className="w-full max-w-2xl space-y-6">
            {isLoading ? (
              <Card className="bg-white/10 backdrop-blur-md border-white/20">
                <CardHeader>
                  <Skeleton className="h-8 w-48 bg-white/20" />
                </CardHeader>
                <CardContent className="space-y-4">
                  <Skeleton className="h-4 w-full bg-white/20" />
                  <Skeleton className="h-4 w-3/4 bg-white/20" />
                </CardContent>
              </Card>
            ) : error ? (
              <Card className="bg-white/10 backdrop-blur-md border-white/20">
                <CardContent className="pt-6">
                  <p className="text-red-300 text-center">
                    Ошибка загрузки профиля. Попробуйте перезагрузить страницу.
                  </p>
                </CardContent>
              </Card>
            ) : displayUser ? (
              <>
                <Card 
                  className="bg-white/10 backdrop-blur-md border-white/20 shadow-2xl hover-elevate transition-all duration-300 animate-fade-in"
                  style={{ animationDelay: '300ms' }}
                  data-testid="card-profile"
                >
                  <CardHeader className="text-center pb-6">
                    <div className="flex justify-center mb-4">
                      <div className="w-24 h-24 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
                        <User className="w-12 h-12 text-white" />
                      </div>
                    </div>
                    <h2 className="text-3xl font-bold text-white" data-testid="text-nickname">
                      {displayUser.nickname}
                    </h2>
                    {displayUser.username && (
                      <p className="text-white/70 flex items-center justify-center gap-2" data-testid="text-username">
                        <SiTelegram className="w-4 h-4" />
                        @{displayUser.username}
                      </p>
                    )}
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {displayUser.quote && (
                      <div className="bg-white/5 rounded-lg p-4 border border-white/10" data-testid="container-quote">
                        <div className="flex items-start gap-3">
                          <Quote className="w-5 h-5 text-purple-300 flex-shrink-0 mt-1" />
                          <p className="text-white/90 italic" data-testid="text-quote">
                            "{displayUser.quote}"
                          </p>
                        </div>
                      </div>
                    )}

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {displayUser.botId && (
                        <div className="bg-white/5 rounded-lg p-4 border border-white/10" data-testid="container-bot-id">
                          <p className="text-white/60 text-sm mb-1">ID в WIRALIS</p>
                          <p className="text-white font-mono text-lg" data-testid="text-bot-id">
                            {displayUser.botId}
                          </p>
                        </div>
                      )}
                      <div className="bg-white/5 rounded-lg p-4 border border-white/10" data-testid="container-telegram-id">
                        <p className="text-white/60 text-sm mb-1">Telegram ID</p>
                        <p className="text-white font-mono text-lg" data-testid="text-telegram-id">
                          {displayUser.telegramId}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card 
                  className="bg-white/10 backdrop-blur-md border-white/20 hover-elevate transition-all duration-300 animate-fade-in"
                  style={{ animationDelay: '500ms' }}
                >
                  <CardContent className="pt-6">
                    <p className="text-white/70 text-center text-sm">
                      Для управления профилем используйте команды в{' '}
                      <a 
                        href="https://t.me/wiralis_bot" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-purple-300 hover:text-purple-200 underline"
                        data-testid="link-telegram-bot"
                      >
                        Telegram-боте
                      </a>
                    </p>
                  </CardContent>
                </Card>
              </>
            ) : null}
          </div>
        </main>

        <footer className="py-6 px-6 text-center animate-fade-in" style={{ animationDelay: '700ms' }}>
          <p className="text-white/60 text-sm" data-testid="text-copyright">
            WIRALIS – Все права защищены
          </p>
        </footer>
      </div>
    </div>
  );
}
