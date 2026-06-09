/**
 * Country → Currency mapping for ParleyLab.
 *
 * Used by the user-settings page and passed to the backend so
 * scenarios use the correct currency symbol and label.
 */

export interface CountryInfo {
  code: string;         // ISO 3166-1 alpha-2
  name: string;
  currency: string;     // ISO 4217 code
  currencySymbol: string;
  currencyName: string;
  flag: string;         // Emoji flag
}

export const COUNTRIES: CountryInfo[] = [
  { code: 'US', name: 'United States',    currency: 'USD', currencySymbol: '$',  currencyName: 'US Dollar',            flag: '🇺🇸' },
  { code: 'GB', name: 'United Kingdom',   currency: 'GBP', currencySymbol: '£',  currencyName: 'British Pound',        flag: '🇬🇧' },
  { code: 'IN', name: 'India',            currency: 'INR', currencySymbol: '₹',  currencyName: 'Indian Rupee',         flag: '🇮🇳' },
  { code: 'EU', name: 'European Union',   currency: 'EUR', currencySymbol: '€',  currencyName: 'Euro',                 flag: '🇪🇺' },
  { code: 'JP', name: 'Japan',            currency: 'JPY', currencySymbol: '¥',  currencyName: 'Japanese Yen',         flag: '🇯🇵' },
  { code: 'CN', name: 'China',            currency: 'CNY', currencySymbol: '¥',  currencyName: 'Chinese Yuan',         flag: '🇨🇳' },
  { code: 'CA', name: 'Canada',           currency: 'CAD', currencySymbol: 'C$', currencyName: 'Canadian Dollar',      flag: '🇨🇦' },
  { code: 'AU', name: 'Australia',        currency: 'AUD', currencySymbol: 'A$', currencyName: 'Australian Dollar',    flag: '🇦🇺' },
  { code: 'DE', name: 'Germany',          currency: 'EUR', currencySymbol: '€',  currencyName: 'Euro',                 flag: '🇩🇪' },
  { code: 'FR', name: 'France',           currency: 'EUR', currencySymbol: '€',  currencyName: 'Euro',                 flag: '🇫🇷' },
  { code: 'BR', name: 'Brazil',           currency: 'BRL', currencySymbol: 'R$', currencyName: 'Brazilian Real',       flag: '🇧🇷' },
  { code: 'KR', name: 'South Korea',      currency: 'KRW', currencySymbol: '₩',  currencyName: 'South Korean Won',     flag: '🇰🇷' },
  { code: 'MX', name: 'Mexico',           currency: 'MXN', currencySymbol: 'MX$',currencyName: 'Mexican Peso',         flag: '🇲🇽' },
  { code: 'SG', name: 'Singapore',        currency: 'SGD', currencySymbol: 'S$', currencyName: 'Singapore Dollar',     flag: '🇸🇬' },
  { code: 'AE', name: 'UAE',              currency: 'AED', currencySymbol: 'د.إ',currencyName: 'UAE Dirham',           flag: '🇦🇪' },
  { code: 'ZA', name: 'South Africa',     currency: 'ZAR', currencySymbol: 'R',  currencyName: 'South African Rand',   flag: '🇿🇦' },
  { code: 'NG', name: 'Nigeria',          currency: 'NGN', currencySymbol: '₦',  currencyName: 'Nigerian Naira',       flag: '🇳🇬' },
  { code: 'SE', name: 'Sweden',           currency: 'SEK', currencySymbol: 'kr', currencyName: 'Swedish Krona',        flag: '🇸🇪' },
  { code: 'CH', name: 'Switzerland',      currency: 'CHF', currencySymbol: 'CHF',currencyName: 'Swiss Franc',          flag: '🇨🇭' },
  { code: 'RU', name: 'Russia',           currency: 'RUB', currencySymbol: '₽',  currencyName: 'Russian Ruble',        flag: '🇷🇺' },
];

/**
 * USD-to-local approximate exchange rates for scaling scenario amounts.
 * These are rough "order of magnitude" conversions — not live rates.
 */
export const EXCHANGE_RATES: Record<string, number> = {
  USD: 1,
  GBP: 0.79,
  INR: 83.5,
  EUR: 0.92,
  JPY: 155,
  CNY: 7.25,
  CAD: 1.36,
  AUD: 1.55,
  BRL: 5.0,
  KRW: 1350,
  MXN: 17.2,
  SGD: 1.34,
  AED: 3.67,
  ZAR: 18.5,
  NGN: 1550,
  SEK: 10.8,
  CHF: 0.88,
  RUB: 92,
};

export function getCountryByCode(code: string): CountryInfo | undefined {
  return COUNTRIES.find(c => c.code === code);
}
