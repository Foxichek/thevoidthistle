import { useState } from 'react';
import { useLocation } from 'wouter';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { Loader2, Sparkles } from 'lucide-react';
import DiamondBackground from '@/components/DiamondBackground';
import FloatingEmojis from '@/components/FloatingEmojis';

const codeSchema = z.object({
  code: z.string()
    .length(6, 'Код должен состоять из 6 символов')
    .regex(/^[A-Z0-9]{6}$/, 'Код должен содержать только латинские буквы и цифры')
    .transform(val => val.toUpperCase()),
});

type CodeForm = z.infer<typeof codeSchema>;

export default function Register() {
  const [, setLocation] = useLocation();
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const form = useForm<CodeForm>({
    resolver: zodResolver(codeSchema),
    defaultValues: {
      code: '',
    },
  });

  const onSubmit = async (data: CodeForm) => {
    setIsLoading(true);
    
    try {
      const response = await fetch('/api/verify-code', {
        method: 'POST',
        body: JSON.stringify({ code: data.code }),
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Ошибка при проверке кода');
      }

      // Сохраняем данные пользователя
      localStorage.setItem('wiralis_user', JSON.stringify(result.user));

      toast({
        title: 'Успешная регистрация!',
        description: `Добро пожаловать, ${result.user.nickname}!`,
      });

      // Переходим на страницу профиля
      setLocation(`/profile/${result.user.id}`);

    } catch (error: any) {
      toast({
        variant: 'destructive',
        title: 'Ошибка',
        description: error.message || 'Не удалось проверить код. Попробуйте еще раз.',
      });
    } finally {
      setIsLoading(false);
    }
  };

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
              className="text-3xl md:text-4xl font-black tracking-wider text-center cursor-pointer"
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
          </div>
        </header>

        <main className="flex-1 flex items-center justify-center px-6 md:px-8 py-12">
          <Card 
            className="w-full max-w-md bg-white/10 backdrop-blur-md border-white/20 shadow-2xl animate-fade-in"
            style={{ animationDelay: '300ms' }}
            data-testid="card-register"
          >
            <CardHeader className="text-center">
              <div className="flex justify-center mb-4">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
                  <Sparkles className="w-8 h-8 text-white" />
                </div>
              </div>
              <CardTitle className="text-2xl font-bold text-white">
                Вход в WIRALIS
              </CardTitle>
              <CardDescription className="text-white/70">
                Введите код из бота для входа
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                  <FormField
                    control={form.control}
                    name="code"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-white">Код регистрации</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            placeholder="ABC123"
                            maxLength={6}
                            className="bg-white/5 border-white/20 text-white placeholder:text-white/40 text-center text-xl tracking-widest uppercase"
                            onChange={(e) => field.onChange(e.target.value.toUpperCase())}
                            data-testid="input-code"
                          />
                        </FormControl>
                        <FormMessage className="text-red-300" />
                      </FormItem>
                    )}
                  />

                  <div className="space-y-3">
                    <Button
                      type="submit"
                      disabled={isLoading}
                      className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white font-semibold"
                      data-testid="button-submit"
                    >
                      {isLoading ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Проверяем код...
                        </>
                      ) : (
                        'Войти'
                      )}
                    </Button>

                    <p className="text-center text-sm text-white/60">
                      Получите код в боте командой{' '}
                      <code className="px-2 py-1 bg-white/10 rounded text-white/80">/web</code>
                    </p>
                  </div>
                </form>
              </Form>
            </CardContent>
          </Card>
        </main>

        <footer className="py-6 px-6 text-center animate-fade-in" style={{ animationDelay: '500ms' }}>
          <p className="text-white/60 text-sm" data-testid="text-copyright">
            WIRALIS – Все права защищены
          </p>
        </footer>
      </div>
    </div>
  );
}
