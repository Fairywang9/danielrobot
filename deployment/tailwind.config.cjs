const path = require('path');
module.exports = {
  content: [path.join(__dirname, '../zhitan/index.html'), path.join(__dirname, '../reports/*.html')],
  theme: {extend: {
    colors: {deepBlue:'#0B1120', techBlue:'#1E293B', tungsten:'#334155', metal:'#94A3B8', vitalOrange:'#F97316', lightGray:'#F1F5F9'},
    fontFamily: {sans:['Inter','Noto Sans SC','sans-serif']},
    animation: {'fade-in-up':'fadeInUp 1s ease-out forwards','pulse-slow':'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite'},
    keyframes: {fadeInUp:{'0%':{opacity:'0',transform:'translateY(20px)'},'100%':{opacity:'1',transform:'translateY(0)'}}}
  }},
  plugins: []
};
