import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import WorkDetails from '../views/WorkDetails.vue'
import ItemProgress from '../views/ItemProgress.vue'
import AddNewWork from '../views/AddNewWork.vue'
import UpdateWork from '../views/UpdateWork.vue'
import MBDetails from '../views/MBDetails.vue'
import Placeholder from '../views/Placeholder.vue'

const routes = [
  { path: '/',               name: 'Dashboard',      component: Dashboard },
  { path: '/work-details',   name: 'Work Details',   component: WorkDetails },
  { path: '/item-progress',  name: 'Item Progress',  component: ItemProgress },
  { path: '/add-new-work',   name: 'Add New Work',   component: AddNewWork },
  { path: '/update-work',    name: 'Update Work',    component: UpdateWork },
  { path: '/mb-details',     name: 'MB Details',     component: MBDetails },
  { path: '/:pathMatch(.*)*', name: 'Placeholder',   component: Placeholder }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
