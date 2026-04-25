FROM node:20-alpine         # Vite, npm, TypeScript compiler 這些工具全都是用JavaScript寫的, 所以需要node環境

WORKDIR /app

COPY package.json ./
RUN npm install             # npm 讀取package.json, 把所有需要的套件(dependencies)都抓下來 (下載React/Vite 到node_modules/)

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
