from pydantic import BaseModel
class TodoItem(BaseModel): title:str; count:int; priority:str; href:str
class PerformanceMetric(BaseModel): title:str; value:str; unit:str=''; trend:str=''; href:str=''
class NavigatorEntry(BaseModel): title:str; description:str; href:str; category:str
class DashboardSummary(BaseModel): date:str; environment:str; todos:list[TodoItem]; performance:list[PerformanceMetric]; navigator:list[NavigatorEntry]; alerts:list[TodoItem]
