(() => {
  const LOCALES = {
    en: "en-US",
    fa: "fa-IR-u-ca-gregory",
  };

  function localeFor(language) {
    return LOCALES[language] || LOCALES.en;
  }

  function validDate(value) {
    if (!value) return null;
    const date = value instanceof Date ? value : new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatDate(value, language = "en", options = {}) {
    const date = validDate(value);
    if (!date) return "";
    return new Intl.DateTimeFormat(localeFor(language), {
      year: "numeric",
      month: "short",
      day: "2-digit",
      ...options,
    }).format(date);
  }

  function formatDateTime(value, language = "en", options = {}) {
    const date = validDate(value);
    if (!date) return "";
    return new Intl.DateTimeFormat(localeFor(language), {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      ...options,
    }).format(date);
  }

  function formatNumber(value, language = "en", options = {}) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "";
    return new Intl.NumberFormat(localeFor(language), options).format(number);
  }

  function formatBytes(value, language = "en", options = {}) {
    const bytes = Number(value);
    if (!Number.isFinite(bytes)) return "";
    if (bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB", "PB"];
    const unitIndex = Math.min(
      Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024)),
      units.length - 1,
    );
    const amount = bytes / (1024 ** unitIndex);
    return `${formatNumber(amount, language, {
      maximumFractionDigits: unitIndex === 0 ? 0 : 1,
      ...options,
    })} ${units[unitIndex]}`;
  }

  function formatDuration(value, language = "en", options = {}) {
    const milliseconds = Number(value);
    if (!Number.isFinite(milliseconds)) return "";
    const absolute = Math.abs(milliseconds);
    const units = [
      ["day", 86400000, "d"],
      ["hour", 3600000, "h"],
      ["minute", 60000, "min"],
      ["second", 1000, "s"],
      ["millisecond", 1, "ms"],
    ];
    const [unit, divisor, shortLabel] =
      units.find(([, size]) => absolute >= size) || units.at(-1);
    const amount = milliseconds / divisor;
    if (options.short) {
      return `${formatNumber(amount, language, {
        maximumFractionDigits: options.maximumFractionDigits ?? 1,
      })} ${shortLabel}`;
    }
    return new Intl.NumberFormat(localeFor(language), {
      style: "unit",
      unit,
      unitDisplay: "long",
      maximumFractionDigits: options.maximumFractionDigits ?? 1,
    }).format(amount);
  }

  window.forgeFormatters = {
    localeFor,
    formatDate,
    formatDateTime,
    formatNumber,
    formatBytes,
    formatDuration,
  };
})();
