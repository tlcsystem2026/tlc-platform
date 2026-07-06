from fastapi import APIRouter
router=APIRouter(prefix='/api/ops',tags=['ops'])
@router.get('/next-actions')
def n(): return {'next_build':'Build031','focus':['matched request to sales post','sales search filters','request batch queue']}
