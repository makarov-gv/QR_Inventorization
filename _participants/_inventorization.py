from pioneer_sdk import Pioneer, Camera
import cv2
import numpy as np
import time


"""Предполагается, что есть ряд с 3 QR-кодами, которые характеризуют содержащиеся предметы. Некоторые из них могут 
отсутствовать, но дрон всё равно попытается их найти. Площадка определяется следующими параметрами:"""
STORAGE_WIDTH = 3
X_INC = float(0.6)  # расстояние между предметами в ряду
HEIGHT = float(0.8)  # высота ряда относительно пола

names = []  # массив для сохранения имён хранящихся предметов, e.g. "Controller"
quantities = []  # массив для сохранения кол-ва хранящихся предметов, e.g. 16


def inventorize(drone, cam):
    """
    Функция инвентаризации. Дрон пролетает ряд за рядом, начиная с крайней верхней левой точки складского стеллажа и
    пытается отсканировать QR-код в каждой ячейке в течении 2.5 секунд, занося её содержимое в два массива:
    массив имён и массив количеств содержащихся предметов. После инвентаризации возвращается на изначальную позицию и
    садится.
    :param drone: экземпляр класса Pioneer
    :param cam: экземпляр класса Camera
    """
    counter = 1
    command_x = float(0)
    detector = cv2.QRCodeDetector()  # инициализация детектора для сканирования QR-кодов
    new_point = True
    while True:
        try:
            camera_frame = cam.get_cv_frame()  # получение кадра с камеры
            if np.sum(camera_frame) == 0:  # если кадр не получен, начинает новую итерацию
                continue
            cv2.imshow('QR Reading', camera_frame)  # вывод изображения на экран

            if new_point:  # если дрон просканировал ячейку, двигается к следующей ячейке
                new_point = False
                drone.go_to_local_point(x=command_x, y=0, z=HEIGHT, yaw=0)

            if drone.point_reached():  # если новая точка достигнута
                timer = time.time()  # записывает время до начала сканирования
                # В цикле дрон пытается найти и просканировать QR-код. Если он его не нашёл в течении 2.5 секунд, то
                # предполагается, что предмета нет. Во время цикла дрон игнорирует нажатие esc и не выводит картинку.
                while True:
                    try:
                        gray = cv2.cvtColor(cam.get_cv_frame(), cv2.COLOR_BGR2GRAY)  # обесцвечивание кадра
                        string, _, _ = detector.detectAndDecode(gray)  # попытка извлечь строку из QR-кода
                        if ((string is not None) and (string != '')) or (time.time() - timer > float(2.5)):
                            break
                    except:
                        continue
                if (string is None) or (string == '') or (len(string.split()) != 2):
                    print("[INFO] На данной полке предмет не найден")
                    # В случае отсутствия предмета на полке, запишем в массивы следующие значения:
                    names.append("None")
                    quantities.append(int(0))
                else:  # если QR-код найден и он в нужном формате (два слова)
                    text = string.split(' ')  # разбиение строки на массив из отдельных элементов, разделённых пробелом
                    print("[INFO] Найден предмет", text[0], "в количестве", text[1])
                    names.append(text[0])  # записываем имя в массив имён
                    quantities.append(int(text[1]))  # записываем кол-во в численном формате в массив кол-в

                if counter == STORAGE_WIDTH:  # если ячейка последняя
                    print("[INFO] Инвентаризация завершена:")
                    print(names)
                    print(quantities)
                    # Возвращаемся на начальную точку и садимся, перед тем как опрашивать пользователя
                    drone.go_to_local_point(x=0, y=0, z=HEIGHT, yaw=0)
                    while True:
                        if drone.point_reached():
                            drone.land()
                            return None
                else:
                    command_x += X_INC
                new_point = True
                counter += 1
        except cv2.error:
            continue

        key_ip = cv2.waitKey(1)  # проверяем нажатие клавиши ESC для предварительного завершения программы
        if key_ip == 27:
            print('[INFO] ESC нажат, программа завершается')
            drone.land()
            time.sleep(5)
            cv2.destroyAllWindows()
            exit(0)


def find_item(drone):
    """
    Функция нахождения и подсвечивания предмета. Рассчитывает, на какое расстояние дрону нужно переместиться, чтобы
    достигнуть нужной ячейки.
    :param drone: экземпляр класса Pioneer
    """
    item_found = False
    from more_itertools import locate
    while True:
        item = input("Какой предмет нужно найти? ")
        if item == "exit":  # команда exit позволит закрыть запрос и завершить программу предварительно
            print("[INFO] Программа завершается предварительно")
            cv2.destroyAllWindows()  # закрывает окно с выводом изображения
            exit(0)
        if item in names:  # если запрошенный предмет находится в массиве имён (т.е. на складе)
            quantity = int(input("В каком количестве? "))
            indexes = list(locate(names, lambda x: x == item))  # находим все ячейки, где встречается этот предмет
            # проверяем, соответствует ли запрошенное кол-во числу предметов в каждой отдельной ячейке
            for i in range(len(indexes)):
                if quantity <= quantities[indexes[i]]:
                    index = indexes[i]  # индекс нужного предмета (его номер в характерных массивах)
                    item_found = True  # флаг, чтобы выйти из внешнего цикла
                    print("Ячейка", index+1, "содержит", item, "в нужном количестве")
                    break
            if item_found:
                break
            print(item, "в нужном количестве не найден, повторите попытку")
        else:
            print("Такого предмета нет на складе, повторите попытку")

    drone.arm()
    drone.takeoff()
    command_x = X_INC*index
    drone.go_to_local_point(x=command_x, y=0, z=HEIGHT, yaw=0)
    while True:
        if drone.point_reached():
            break

    print("Дрон подсвечивает ячейку")
    drone.led_control(r=0, g=255, b=0)
    time.sleep(3)
    drone.led_control(r=0, g=0, b=0)


if __name__ == '__main__':
    pioneer_mini = Pioneer(logger=False)  # pioneer_mini как экземпляр класса Pioneer
    pioneer_mini.arm()
    pioneer_mini.takeoff()
    camera = Camera()  # camera как экземпляр класса Camera

    inventorize(pioneer_mini, camera)

    find_item(pioneer_mini)

    pioneer_mini.land()
    time.sleep(5)
    cv2.destroyAllWindows()  # закрывает окно с выводом изображения
    exit(0)
