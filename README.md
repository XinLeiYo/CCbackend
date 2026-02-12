# CCbackend - Equipment Management API

A Flask-based REST API backend for equipment management with JWT authentication, image upload capabilities, and MSSQL Server database integration.

## Features

- **User Authentication**
  - User registration and login with JWT tokens
  - Password hashing with Werkzeug
  - Password reset functionality
  - Token-based authentication with 60-minute expiration

- **Equipment Management**
  - CRUD operations for equipment records
  - Batch update support
  - Equipment status tracking and statistics
  - Complete audit log/history for each equipment item
  - Automatic update counter

- **Issue Reporting**
  - Submit issue reports for equipment
  - Multiple image upload support (PNG, JPG, JPEG, GIF)
  - Report status tracking (待處理/處理中/已完成)
  - Report processing with notes and timestamps

- **Cross-Origin Support**
  - CORS enabled for frontend integration
  - Preflight request handling

## Tech Stack

- **Framework**: Flask 3.x
- **Database**: Microsoft SQL Server (MSSQL)
- **Authentication**: Flask-JWT-Extended
- **Database Driver**: pyodbc (ODBC Driver 17 for SQL Server)
- **Password Security**: Werkzeug (generate_password_hash, check_password_hash)
- **Environment Management**: python-dotenv
- **Server**: Gevent (production-ready WSGI server)
- **Containerization**: Docker & Docker Compose

## Prerequisites

- Python 3.10+
- SQL Server 2019+ or SQL Server Express
- ODBC Driver 17 for SQL Server
- Docker (optional, for containerized deployment)

## Installation

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd CCbackend
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file in the root directory:
   ```env
   # Database Configuration
   DB_SERVER_IP=192.168.2.65
   DB_INSTANCE=SQLEXPRESS
   DB_DATABASE=YOYODB
   DB_USERNAME=your_username
   DB_PASSWORD=your_password

   # JWT Configuration
   JWT_SECRET_KEY=your-secret-key-here
   ```

5. **Create the upload directory**
   ```bash
   mkdir -p static/uploads
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

   The API will be available at `http://localhost:5172`

### Docker Deployment

1. **Using Docker Compose** (recommended)
   ```bash
   docker-compose up -d
   ```

   This will start:
   - Backend API on port `5172`
   - MSSQL Server on port `1434`

2. **Build and run manually**
   ```bash
   docker build -t cc-backend .
   docker run -p 5172:5172 cc-backend
   ```

## Database Schema

The application expects the following tables in the MSSQL database:

### CC_USER
- `USER_NAME` (Primary Key)
- `PASSWORD` (hashed)

### CC_MASTER
- `CCM_ID` (Primary Key) - Equipment ID
- `CC_SIZE` - Equipment size
- `BOX_ID` - Box identifier
- `USER_NAME` - User name
- `CC_STARTTIME` - Start time
- `UPD_CNT` - Update counter

### CC_LOG
- `CCL_ID` (Auto-increment Primary Key)
- `CC_ID_FK` (Foreign Key to CC_MASTER)
- `INPUT_DATE` - Input date
- `CC_STATUS` - Status
- `CC_SUBSTATUS` - Sub-status
- `UPDATE_BY` - Updated by (username)
- `UPDATE_TIME` - Update timestamp
- `COMMENT` - Comments

### CC_REPORT
- `ID` (Auto-increment Primary Key)
- `CCM_ID_FK` (Foreign Key to CC_MASTER)
- `REPORTER` - Reporter username
- `REPORT_TIME` - Report timestamp
- `ISSUE_TYPE` - Issue type
- `ISSUE_INFO` - Issue description
- `IMAGE_PATH` - JSON array of image paths
- `STATUS` - Report status
- `PROCESSER` - Processor username
- `PROCESS_TIME` - Processing timestamp
- `PROCESS_NOTES` - Processing notes

## API Endpoints

### Authentication

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/auth/login` | User login | No |
| POST | `/api/register` | User registration | No |
| POST | `/api/auth/verify_username` | Verify username exists | No |
| POST | `/api/auth/forgot_password` | Forgot password | No |
| POST | `/api/auth/reset_password_no_auth` | Reset password without auth | No |
| PUT | `/api/reset_password` | Reset password (authenticated) | Yes |

### Equipment Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/equipment` | Get all equipment | Yes |
| POST | `/api/equipment` | Add new equipment | Yes |
| PUT | `/api/equipment/<ccm_id>` | Update equipment | Yes |
| PUT | `/api/equipment/batch` | Batch update equipment | Yes |
| DELETE | `/api/equipment/<ccm_id>` | Delete equipment | Yes |
| GET | `/api/equipment/status_counts` | Get status statistics | Yes |
| GET | `/api/equipment/logs/<ccm_id>` | Get equipment log history | Yes |

### Issue Reporting

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/report/upload` | Submit issue report with images | Yes |
| GET | `/api/reports` | Get all reports | Yes |
| PUT | `/api/report/<report_id>` | Update report status | Yes |
| DELETE | `/api/report/<report_id>` | Delete report | Yes |
| GET | `/uploads/<filename>` | Serve uploaded images | No |

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DB_SERVER_IP` | Database server IP address | Yes |
| `DB_INSTANCE` | SQL Server instance name | Yes |
| `DB_DATABASE` | Database name | Yes |
| `DB_USERNAME` | Database username | Yes |
| `DB_PASSWORD` | Database password | Yes |
| `JWT_SECRET_KEY` | Secret key for JWT tokens | Yes |

### Application Settings

- **Upload folder**: `static/uploads`
- **Max file size**: 16 MB
- **Allowed file types**: PNG, JPG, JPEG, GIF
- **JWT token expiration**: 60 minutes
- **Server host**: 0.0.0.0
- **Server port**: 5172

## Example Requests

### Login
```bash
curl -X POST http://localhost:5172/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "password123"}'
```

### Get Equipment (with JWT)
```bash
curl -X GET http://localhost:5172/api/equipment \
  -H "Authorization: Bearer <your_jwt_token>"
```

### Add Equipment
```bash
curl -X POST http://localhost:5172/api/equipment \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "CCM_ID": "EQ001",
    "CC_SIZE": "Large",
    "BOX_ID": "BOX001",
    "USER_NAME": "user1",
    "CC_STARTTIME": "2026-02-12 10:00:00",
    "CC_STATUS": "正常",
    "CC_SUBSTATUS": "使用中",
    "COMMENT": "Initial setup"
  }'
```

### Submit Issue Report with Images
```bash
curl -X POST http://localhost:5172/api/report/upload \
  -H "Authorization: Bearer <your_jwt_token>" \
  -F "ccm_id=EQ001" \
  -F "issue_type=損壞" \
  -F "issue_description=Equipment malfunction" \
  -F "images=@image1.jpg" \
  -F "images=@image2.jpg"
```

## Development

### Project Structure
```
CCbackend/
├── app.py                 # Main Flask application
├── models.py             # Database models (if any)
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose setup
├── .env                 # Environment variables (not in git)
├── static/
│   └── uploads/        # Uploaded images
└── .venv/              # Virtual environment
```

### Running in Debug Mode

The application runs in debug mode by default when started with `python app.py`. For production, the gevent WSGI server is used automatically.

## Deployment

### Production Deployment

1. Set `debug=False` in production
2. Use environment variables for sensitive data
3. Set up proper firewall rules
4. Enable HTTPS/SSL
5. Use a reverse proxy (nginx/Apache) if needed
6. Set up database backups
7. Monitor logs and performance

### Port Configuration

- Default API port: `5172`
- Database port (Docker): `1434`
- Database port (local): `1433`

## Security Considerations

- All passwords are hashed using Werkzeug's `generate_password_hash`
- JWT tokens expire after 60 minutes
- File uploads are restricted to specific image formats
- Maximum upload size is 16 MB
- SQL queries use parameterized statements to prevent SQL injection
- CORS is enabled (configure allowed origins in production)

## Troubleshooting

### Database Connection Issues
- Verify SQL Server is running
- Check firewall settings
- Ensure ODBC Driver 17 is installed
- Verify connection string in `.env`

### Docker Issues
- Ensure Docker daemon is running
- Check port conflicts
- View logs: `docker-compose logs -f`

### Image Upload Issues
- Verify `static/uploads` directory exists and has write permissions
- Check file size (max 16 MB)
- Ensure file type is allowed (PNG, JPG, JPEG, GIF)

## License

[Specify your license here]

## Contributors

[Add contributors here]
