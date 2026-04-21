import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import react from 'eslint-plugin-react';

export default [
  {
    ignores: ['dist/**', 'node_modules/**', '.tanstack/**', 'src/components/ui/**'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx,js,jsx}'],
    plugins: {
      react,
    },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      'react/forbid-elements': [
        'error',
        {
          forbid: [
            {
              element: 'button',
              message:
                'Use the shadcn <Button> component from @/components/ui/button instead.',
            },
          ],
        },
      ],
    },
  },
];
