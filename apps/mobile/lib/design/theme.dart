import 'package:flutter/material.dart';

abstract final class Stamp {
  static const parchment = Color(0xFFF3EFE6);
  static const paper = Color(0xFFFBF8F1);
  static const pine = Color(0xFF17352E);
  static const brass = Color(0xFFB8873C);
  static const deepBrass = Color(0xFF8A6216);
  static const ink = Color(0xFF1A1F1C);
  static const oxide = Color(0xFFA0392C);

  static ThemeData theme(bool dark) {
    final scheme = ColorScheme.fromSeed(
      seedColor: pine,
      brightness: dark ? Brightness.dark : Brightness.light,
    ).copyWith(
      primary: dark ? const Color(0xFFD4A557) : pine,
      surface: dark ? const Color(0xFF1A2320) : paper,
      onSurface: dark ? const Color(0xFFEDE8DC) : ink,
      secondary: dark ? const Color(0xFFD4A557) : deepBrass,
      outline: dark ? const Color(0xFF48544B) : const Color(0xFFDFD8C8),
      error: dark ? const Color(0xFFE0897B) : oxide,
    );
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      fontFamily: 'Karla',
      scaffoldBackgroundColor: dark ? const Color(0xFF121916) : parchment,
    );
    return base.copyWith(
      textTheme: base.textTheme.copyWith(
        displaySmall: TextStyle(
          fontFamily: 'Spectral',
          fontSize: 38,
          height: 1.12,
          color: scheme.onSurface,
        ),
        headlineMedium: TextStyle(
          fontFamily: 'Spectral',
          fontSize: 30,
          height: 1.22,
          color: scheme.onSurface,
        ),
        titleLarge: TextStyle(
          fontFamily: 'Spectral',
          fontSize: 23,
          height: 1.3,
          color: scheme.onSurface,
        ),
        bodyLarge: TextStyle(
          fontFamily: 'Karla',
          fontSize: 17,
          height: 1.5,
          color: scheme.onSurface,
        ),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: base.scaffoldBackgroundColor,
        foregroundColor: scheme.onSurface,
        scrolledUnderElevation: 0,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: scheme.outline),
        ),
        contentPadding: const EdgeInsets.all(20),
      ),
    );
  }
}
