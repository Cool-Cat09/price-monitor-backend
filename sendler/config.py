from pydantic_settings import BaseSettings, SettingsConfigDict


class SendlerSettings(BaseSettings):
    sendler_pass: str
    sendler_email: str


    model_config = SettingsConfigDict(
        env_file = 'sendler.env',
        env_file_encoding = 'utf-8',
        extra = 'ignore',
        case_sensitive = False,
    )
    

class DatabaseSettings(BaseSettings):
    database_pass: str = 'postgres'
    database_user: str = 'postgres'
    database_host: str = 'db'
    database_host_dev: str = 'localhost'
    database_port: int = 5432
    database_name: str = 'sendler'


    model_config = SettingsConfigDict(
        env_file = 'sendler.env',
        env_file_encoding = 'utf-8',
        extra = 'ignore',
        pyproject_toml_depth = 2,
        case_sensitive = False,
    )


    @property
    def database_url(self):
        return (
            f'postgresql+asyncpg://{self.database_user}:{self.database_pass}'
            f'@{self.database_host}:{self.database_port}/{self.database_name}'
        )
    
    @property
    def database_url_to_host(self):
        """using to work with bd in manual mode"""
        return (
            f'postgresql+asyncpg://{self.database_user}:{self.database_pass}'
            f'@{self.database_host_dev}:{self.database_port}/{self.database_name}'
        )


class RabbitMQSettings(BaseSettings):
    rabbit_pass: str = 'guest'
    rabbit_login: str = 'guest'
    rabbit_host: str = 'rabbit'
    rabbit_host_dev: str = 'localhost'
    rabbit_port: int = 5672


    model_config = SettingsConfigDict(
        env_file = 'sendler.env',
        env_file_encoding = 'utf-8',
        extra = 'ignore',
        case_sensitive = False,
    )

    @property
    def rabbitmq_url(self):
        return (
            f'amqp://{self.rabbit_login}:{self.rabbit_pass}'
            f'@{self.rabbit_host}:{self.rabbit_port}'
        )
    
    @property
    def rabbit_url_to_dev(self):
        return (
            f'amqp://{self.rabbit_login}:{self.rabbit_pass}'
            f'@{self.rabbit_host}:{self.rabbit_port}'
        )
    

rabbit_settings = RabbitMQSettings()

sendler_settings = SendlerSettings() # type: ignore

database_settings = DatabaseSettings()