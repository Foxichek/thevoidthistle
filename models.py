# models.py

from sqlalchemy import (
    Column, Integer, String, TIMESTAMP, ForeignKey, BigInteger, func,
    CheckConstraint, Boolean, JSON, Float, Text, Date
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from database import Base

# ============================================================================
# ОСНОВНЫЕ МОДЕЛИ
# ============================================================================

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    nickname = Column(String, nullable=False)
    username = Column(String, nullable=True)
    bot_id = Column(String(4), unique=True, nullable=False, index=True)
    role = Column(String, nullable=False, server_default='player')
    quote = Column(String(150), nullable=True)
    banner_file_id = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    recovered_from_legacy = Column(Boolean, default=False, nullable=False)
    
    profile_visibility = Column(JSON, nullable=False, server_default='{}')
    active_theme_id = Column(Integer, ForeignKey('theme_definitions.id', ondelete='SET NULL'), nullable=True)
    active_badge_id = Column(Integer, ForeignKey('badge_definitions.id', ondelete='SET NULL'), nullable=True)

    currency_crystals = Column(BigInteger, nullable=False, server_default='0')
    currency_tokens = Column(BigInteger, nullable=False, server_default='0')
    currency_globals = Column(BigInteger, nullable=False, server_default='0')
    currency_moons = Column(BigInteger, nullable=False, server_default='0')

    level = Column(Integer, nullable=False, server_default='1')
    experience = Column(BigInteger, nullable=False, server_default='0')
    unclaimed_rewards = Column(Integer, nullable=False, server_default='0')
    ascension = Column(Integer, nullable=False, server_default='0')
    
    natural_energy = Column(Float, nullable=False, server_default='100.0')
    purchased_energy = Column(BigInteger, nullable=False, server_default='0')
    energy_last_updated = Column(TIMESTAMP, nullable=False, server_default=func.now())

    payment_rank_points = Column(Integer, nullable=False, server_default='0')
    payment_warnings = Column(Integer, nullable=False, server_default='0')
    payment_consecutive_fails = Column(Integer, nullable=False, server_default='0')
    payment_rank_initialized = Column(Boolean, nullable=False, server_default='false')
    payment_blocked_until = Column(TIMESTAMP, nullable=True)

    # --- Связи (Relationships) ---
    votes_given = relationship("UserRating", foreign_keys="[UserRating.voter_telegram_id]", cascade="all, delete-orphan", back_populates="voter")
    votes_received = relationship("UserRating", foreign_keys="[UserRating.target_telegram_id]", cascade="all, delete-orphan", back_populates="target")
    manual_payments = relationship("ManualPayment", cascade="all, delete-orphan", back_populates="user")
    
    smeltery_furnaces = relationship("UserSmeltery", cascade="all, delete-orphan", back_populates="user")
    material_inventory = relationship("UserMaterialInventory", cascade="all, delete-orphan", back_populates="user")
    discovered_materials = relationship("UserDiscoveredMaterial", cascade="all, delete-orphan", back_populates="user")

    abyss_progress = relationship("UserMineProgress", uselist=False, cascade="all, delete-orphan", back_populates="user")
    ore_inventory = relationship("UserOreInventory", cascade="all, delete-orphan", back_populates="user")
    discovered_ores = relationship("UserDiscoveredOre", cascade="all, delete-orphan", back_populates="user")
    location_states = relationship("UserLocationState", cascade="all, delete-orphan", back_populates="user")
    location_progresses = relationship("UserLocationProgress", cascade="all, delete-orphan", back_populates="user")
    
    unlocked_themes = relationship("UserTheme", cascade="all, delete-orphan", back_populates="user")
    halloween_progress = relationship("HalloweenEventProgress", uselist=False, cascade="all, delete-orphan", back_populates="user")
    unlocked_badges = relationship("UserBadge", cascade="all, delete-orphan", back_populates="user")
    
    active_theme = relationship("ThemeDefinition", foreign_keys=[active_theme_id])
    active_badge = relationship("BadgeDefinition", foreign_keys=[active_badge_id])
    
    reputation = relationship("UserReputation", uselist=False, cascade="all, delete-orphan", back_populates="user")
    
    # --- НОВЫЕ СВЯЗИ ---
    user_settings = relationship("UserSettings", uselist=False, cascade="all, delete-orphan", back_populates="user")
    user_stats = relationship("UserStats", uselist=False, cascade="all, delete-orphan", back_populates="user")


class UserReputation(Base):
    __tablename__ = 'user_reputation'
    
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    level = Column(Integer, nullable=False, server_default='0')
    reputation_points = Column(BigInteger, nullable=False, server_default='0')
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="reputation")


class UserRating(Base):
    __tablename__ = 'user_ratings'
    voter_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    target_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    vote_type = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint('vote_type IN (1, -1)', name='check_vote_type'),)
    voter = relationship("User", foreign_keys=[voter_telegram_id], back_populates="votes_given")
    target = relationship("User", foreign_keys=[target_telegram_id], back_populates="votes_received")

class BotState(Base):
    __tablename__ = 'bot_state'
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)

# ============================================================================
# НОВЫЕ МОДЕЛИ
# ============================================================================

class UserSettings(Base):
    __tablename__ = 'user_settings'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    
    # Настройки уведомлений
    notify_level_up = Column(Boolean, nullable=False, server_default='true')
    notify_event_start = Column(Boolean, nullable=False, server_default='true')
    
    # Настройки интерфейса
    interface_language = Column(String(10), nullable=False, server_default='ru')
    
    # Настройки приватности
    show_online_status = Column(Boolean, nullable=False, server_default='true')
    
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="user_settings")

class UserStats(Base):
    __tablename__ = 'user_stats'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    
    # Статистика по активности
    total_expeditions = Column(BigInteger, nullable=False, server_default='0')
    total_smelts = Column(BigInteger, nullable=False, server_default='0')
    
    # Статистика по ресурсам
    crystals_earned = Column(BigInteger, nullable=False, server_default='0')
    tokens_earned = Column(BigInteger, nullable=False, server_default='0')
    
    # Статистика по рейтингу
    upvotes_received = Column(Integer, nullable=False, server_default='0')
    downvotes_received = Column(Integer, nullable=False, server_default='0')
    
    last_active = Column(TIMESTAMP, server_default=func.now())
    
    user = relationship("User", back_populates="user_stats")

# ============================================================================
# МОДЕЛИ ИВЕНТОВ
# ============================================================================

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    module_name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    event_emoji = Column(String(10), nullable=False, server_default='🎉')
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    notification_state = Column(String(20), nullable=False, server_default='pending')

# ============================================================================
# МОДЕЛИ СИСТЕМЫ БЕЙДЖЕЙ
# ============================================================================

class BadgeDefinition(Base):
    __tablename__ = 'badge_definitions'
    id = Column(Integer, primary_key=True)
    code_name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    emoji = Column(String(10), nullable=False)
    category = Column(String(50), nullable=False, server_default='general')
    rarity = Column(String(20), nullable=False, server_default='common')
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class UserBadge(Base):
    __tablename__ = 'user_badges'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    badge_id = Column(Integer, ForeignKey('badge_definitions.id', ondelete='CASCADE'), primary_key=True)
    unlocked_at = Column(TIMESTAMP, server_default=func.now())
    unlock_context = Column(Text, nullable=True)
    user = relationship("User", back_populates="unlocked_badges")
    badge = relationship("BadgeDefinition")

# ============================================================================
# МОДЕЛИ СИСТЕМЫ ТЕМ ОФОРМЛЕНИЯ
# ============================================================================

class ThemeDefinition(Base):
    __tablename__ = 'theme_definitions'
    id = Column(Integer, primary_key=True)
    code_name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    emoji = Column(String(10), nullable=False, server_default='🎨')
    rarity = Column(String(20), nullable=False, server_default='common')
    profile_styles = Column(JSONB, nullable=False, server_default='{}')
    inventory_styles = Column(JSONB, nullable=False, server_default='{}')
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class UserTheme(Base):
    __tablename__ = 'user_themes'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    theme_id = Column(Integer, ForeignKey('theme_definitions.id', ondelete='CASCADE'), primary_key=True)
    unlocked_at = Column(TIMESTAMP, server_default=func.now())
    user = relationship("User", back_populates="unlocked_themes")
    theme = relationship("ThemeDefinition")

# ============================================================================
# МОДЕЛИ ХЕЛЛОУИНСКОГО ИВЕНТА (v4.0 - Badge Integration)
# ============================================================================

class HalloweenEventProgress(Base):
    __tablename__ = 'halloween_event_progress'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    
    quests_completed = Column(Integer, nullable=False, server_default='0') 
    
    last_quest_date = Column(Date, nullable=True)
    daily_attempts_left = Column(Integer, nullable=False, server_default='3')
    
    reward_claimed = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="halloween_progress")


# ============================================================================
# МОДЕЛИ БЕЗДНЫ (РЕВОРК v3.0 "ГЛУБИНА И ЗНАНИЕ")
# ============================================================================

class Ore(Base):
    __tablename__ = 'ores'
    id = Column(Integer, primary_key=True)
    code_name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    emoji = Column(String(10), nullable=False)
    category = Column(String(1), nullable=False, server_default='О')
    exchange_rate = relationship("OreExchangeRate", uselist=False, cascade="all, delete-orphan", back_populates="ore")
    __table_args__ = (CheckConstraint("category IN ('О', 'М', 'К', 'Э')", name='check_ore_category'),)
    
class MineLocation(Base):
    __tablename__ = 'mine_locations'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, server_default='Неизведанный сектор')
    depth = Column(Integer, nullable=False, index=True)
    parent_ids = Column(ARRAY(Integer), nullable=False, server_default='{}')
    unlock_cost_rp = Column(Integer, nullable=False, server_default='0')
    energy_cost = Column(Integer, nullable=False, server_default='10')
    min_time = Column(Integer, nullable=False)
    max_time = Column(Integer, nullable=False)
    avg_ore_yield = Column(Integer, nullable=False)
    min_experience = Column(Integer, nullable=False)
    research_tree = Column(JSONB, nullable=False, server_default='{}')
    ores = relationship("MineLocationOre", back_populates="location", cascade="all, delete-orphan")

class MineLocationOre(Base):
    __tablename__ = 'mine_location_ores'
    location_id = Column(Integer, ForeignKey('mine_locations.id', ondelete='CASCADE'), primary_key=True)
    ore_id = Column(Integer, ForeignKey('ores.id', ondelete='CASCADE'), primary_key=True)
    initial_quantity = Column(BigInteger, nullable=False)
    location = relationship("MineLocation", back_populates="ores")
    ore = relationship("Ore")

class UserMineProgress(Base):
    __tablename__ = 'user_mine_progress'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    current_location_id = Column(Integer, nullable=False, server_default='1')
    unlocked_location_ids = Column(ARRAY(Integer), nullable=False, server_default='{1}')
    research_balance = Column(BigInteger, nullable=False, server_default='0')
    user = relationship("User", back_populates="abyss_progress")

class UserLocationProgress(Base):
    __tablename__ = 'user_location_progress'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    location_id = Column(Integer, primary_key=True)
    clear_progress = Column(Float, default=0.0, nullable=False)
    total_expeditions = Column(Integer, default=0, nullable=False)
    unlocked_research = Column(ARRAY(String), nullable=False, server_default='{}')
    user = relationship("User", back_populates="location_progresses")

class UserOreInventory(Base):
    __tablename__ = 'user_ore_inventory'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    ore_id = Column(Integer, ForeignKey('ores.id', ondelete='CASCADE'), primary_key=True)
    quantity = Column(BigInteger, default=0, nullable=False)
    user = relationship("User", back_populates="ore_inventory")
    ore = relationship("Ore")

class UserDiscoveredOre(Base):
    __tablename__ = 'user_discovered_ores'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    ore_id = Column(Integer, ForeignKey('ores.id', ondelete='CASCADE'), primary_key=True)
    user = relationship("User", back_populates="discovered_ores")
    ore = relationship("Ore")

class UserLocationState(Base):
    __tablename__ = 'user_location_state'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    location_id = Column(Integer, primary_key=True)
    ore_id = Column(Integer, ForeignKey('ores.id', ondelete='CASCADE'), primary_key=True)
    remaining_quantity = Column(BigInteger, nullable=False)
    user = relationship("User", back_populates="location_states")
    ore = relationship("Ore")

class OreExchangeRate(Base):
    __tablename__ = 'ore_exchange_rates'
    ore_id = Column(Integer, ForeignKey('ores.id', ondelete='CASCADE'), primary_key=True)
    crystals_rate = Column(Integer, default=0, nullable=False)
    crystals_probability = Column(Float, default=0.0, nullable=False)
    tokens_rate = Column(Integer, default=0, nullable=False)
    tokens_probability = Column(Float, default=0.0, nullable=False)
    globals_rate = Column(Integer, default=0, nullable=False)
    globals_probability = Column(Float, default=0.0, nullable=False)
    moons_rate = Column(Integer, default=0, nullable=False)
    moons_probability = Column(Float, default=0.0, nullable=False)
    trend = Column(Integer, default=0, nullable=False)
    volatility = Column(Float, default=0.0, nullable=False)
    inactivity_cycles = Column(Integer, default=0, server_default='0', nullable=False)
    ore = relationship("Ore", back_populates="exchange_rate")

class OreExchangeVolume(Base):
    __tablename__ = 'ore_exchange_volume'
    ore_id = Column(Integer, ForeignKey('ores.id', ondelete='CASCADE'), primary_key=True)
    total_volume = Column(BigInteger, default=0, server_default='0', nullable=False)
    ore = relationship("Ore")

class MineGlobalEvent(Base):
    __tablename__ = 'mine_global_events'
    id = Column(Integer, primary_key=True)
    code_name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    modifiers = Column(JSONB, nullable=False, server_default='{}')

class MineAnomaly(Base):
    __tablename__ = 'mine_anomalies'
    id = Column(Integer, primary_key=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    min_depth = Column(Integer, nullable=False, default=1)
    max_depth = Column(Integer, nullable=False, default=999)
    spawn_chance = Column(Float, nullable=False, default=0.1)
    options = Column(JSONB, nullable=False, server_default='[]')

# ============================================================================
# ПРОЧИЕ МОДЕЛИ
# ============================================================================

class ManualPayment(Base):
    __tablename__ = 'manual_payments'
    id = Column(Integer, primary_key=True)
    payment_code = Column(String, unique=True, nullable=False, index=True)
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False)
    energy_amount = Column(Integer, nullable=True) 
    item_details = Column(Text, nullable=True)
    status = Column(String, nullable=False, default='pending')
    payment_type = Column(String, nullable=False, default='manual')
    original_price = Column(Integer, nullable=False)
    final_price = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    expires_at = Column(TIMESTAMP, nullable=True)
    user = relationship("User", back_populates="manual_payments")

class Material(Base):
    __tablename__ = 'materials'
    id = Column(Integer, primary_key=True)
    code_name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    emoji = Column(String(10), nullable=False)
    tier = Column(Integer, nullable=False)
    recipe = Column(JSONB, nullable=False)
    min_experience = Column(Integer, nullable=False)
    max_experience = Column(Integer, nullable=False)
    smelting_time_minutes = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    
class UserSmeltery(Base):
    __tablename__ = 'user_smeltery'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    furnace_id = Column(Integer, primary_key=True)
    level = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    process_type = Column(String(20), nullable=True)
    material_id = Column(Integer, ForeignKey('materials.id'), nullable=True)
    active_recipe_data = Column(JSONB, nullable=True)
    start_time = Column(TIMESTAMP, nullable=True)
    end_time = Column(TIMESTAMP, nullable=True)
    is_successful = Column(Boolean, nullable=True)
    user = relationship("User", back_populates="smeltery_furnaces")
    material = relationship("Material")

class UserMaterialInventory(Base):
    __tablename__ = 'user_material_inventory'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    material_id = Column(Integer, ForeignKey('materials.id', ondelete='CASCADE'), primary_key=True)
    quantity = Column(BigInteger, default=0, nullable=False)
    user = relationship("User", back_populates="material_inventory")
    material = relationship("Material")

class UserDiscoveredMaterial(Base):
    __tablename__ = 'user_discovered_materials'
    user_telegram_id = Column(BigInteger, ForeignKey('users.telegram_id', ondelete='CASCADE'), primary_key=True)
    material_id = Column(Integer, ForeignKey('materials.id', ondelete='CASCADE'), primary_key=True)
    user = relationship("User", back_populates="discovered_materials")
    material = relationship("Material")
