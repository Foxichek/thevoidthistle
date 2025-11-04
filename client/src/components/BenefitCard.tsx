import { LucideIcon } from 'lucide-react';
import { useState } from 'react';

interface BenefitCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  delay?: number;
  onClick?: () => void;
}

export default function BenefitCard({ icon: Icon, title, description, delay = 0, onClick }: BenefitCardProps) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const card = e.currentTarget;
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    
    const tiltX = ((y - centerY) / centerY) * (onClick ? -8 : -4);
    const tiltY = ((x - centerX) / centerX) * (onClick ? 8 : 4);
    
    setTilt({ x: tiltX, y: tiltY });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  return (
    <div
      className={`bg-white/10 backdrop-blur-xl border border-white/30 rounded-xl p-5 md:p-6 transition-all duration-300 ${
        onClick ? 'cursor-pointer hover-elevate' : 'hover-elevate'
      }`}
      style={{ 
        animationDelay: `${delay}ms`,
        transform: onClick ? `perspective(1000px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg) scale(${tilt.x || tilt.y ? 1.02 : 1})` : `perspective(1000px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        boxShadow: `
          0 8px 32px rgba(139, 92, 246, 0.15),
          0 4px 16px rgba(0, 0, 0, 0.1),
          inset 0 1px 0 rgba(255, 255, 255, 0.15),
          inset 0 -1px 0 rgba(0, 0, 0, 0.1)
        `,
        background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.12) 0%, rgba(255, 255, 255, 0.08) 100%)',
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      data-testid={`card-benefit-${title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="flex flex-col items-center text-center space-y-3 md:space-y-4">
        <div className="w-12 h-12 md:w-14 md:h-14 rounded-lg bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center shadow-lg">
          <Icon className="w-6 h-6 md:w-7 md:h-7 text-white" />
        </div>
        <h3 className="text-base md:text-lg font-semibold text-white">
          {title}
        </h3>
        <p className="text-white/70 text-sm leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  );
}
