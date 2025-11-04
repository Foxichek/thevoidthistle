import { sql } from "drizzle-orm";
import { pgTable, text, varchar, timestamp, bigint, boolean, integer } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// Коды регистрации для связи сайта и бота
export const registrationCodes = pgTable("registration_codes", {
  code: varchar("code", { length: 6 }).primaryKey(),
  telegramId: bigint("telegram_id", { mode: "number" }).notNull(),
  createdAt: timestamp("created_at").notNull().default(sql`now()`),
  expiresAt: timestamp("expires_at").notNull(),
  isUsed: boolean("is_used").notNull().default(false),
  usedAt: timestamp("used_at"),
});

// Пользователи WIRALIS (импортированные из бота)
export const wiralisUsers = pgTable("wiralis_users", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  telegramId: bigint("telegram_id", { mode: "number" }).notNull().unique(),
  nickname: text("nickname").notNull(),
  username: text("username"),
  quote: text("quote"),
  botId: varchar("bot_id", { length: 4 }),
  registeredAt: timestamp("registered_at").notNull().default(sql`now()`),
});

// Схемы для валидации
export const insertRegistrationCodeSchema = createInsertSchema(registrationCodes).pick({
  code: true,
  telegramId: true,
  expiresAt: true,
});

export const insertWiralisUserSchema = createInsertSchema(wiralisUsers).omit({
  id: true,
  registeredAt: true,
});

export const verifyCodeSchema = z.object({
  code: z.string().length(6).regex(/^[A-Z0-9]{6}$/, "Код должен состоять из 6 латинских букв или цифр"),
});

// Типы
export type InsertRegistrationCode = z.infer<typeof insertRegistrationCodeSchema>;
export type RegistrationCode = typeof registrationCodes.$inferSelect;
export type InsertWiralisUser = z.infer<typeof insertWiralisUserSchema>;
export type WiralisUser = typeof wiralisUsers.$inferSelect;
export type VerifyCode = z.infer<typeof verifyCodeSchema>;
