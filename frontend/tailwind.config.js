/** @type {import('tailwindcss').Config} */
export default {
  // Tema escuro acionado pelo atributo data-theme="dark" (definido em useTheme).
  // Sem isso, as classes dark:* nunca eram ativadas e o botão de tema parecia morto.
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
