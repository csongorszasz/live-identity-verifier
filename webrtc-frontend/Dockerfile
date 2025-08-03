# Use an official Node.js lightweight image to build the app
FROM node:18-alpine AS build

# Set the working directory inside the container
WORKDIR /app

# Copy package.json and package-lock.json into the container
COPY package*.json /app/

# Install dependencies
RUN npm install

# Copy the rest of the app's source code into the container
COPY . /app/

# Build the app for production
RUN npm run build

# Use an Nginx image to serve the built React app
FROM nginx:stable-alpine

# Copy the NGINX configuration file
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the build output from the previous stage into Nginx web server
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

# Start Nginx when the container runs
CMD ["nginx", "-g", "daemon off;"]
