/** @type {import('tailwindcss').Config} */
module.exports = {
    theme: {
      container: {
        center: true,
        padding: '2rem',
      },
    },
    content: ["./src/**/*.{html,js}", "./dist/*.{html,js}"],
    plugins: [require("daisyui")],
  }